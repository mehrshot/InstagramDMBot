"""The DM pipeline: record incoming webhook events, then reply after a short debounce.

    webhook ──► handle_event ──(enqueue, delayed)──► reply_to_conversation ──► Instagram

Decisions that are easy to get wrong live here:
- Meta retries webhooks, so everything is idempotent on the message id (`mid`).
- Customers send bursts of short messages; each schedules a reply, but only the job for the
  newest message actually answers.
- When the owner answers by hand the bot steps back for `shop.handoff_pause_minutes`. Our own
  sends also come back as echoes and must not be mistaken for the owner.
"""

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.queue import Queue
from app.core.security import decrypt_secret
from app.core.timeutil import as_utc, utcnow
from app.models import Conversation, InstagramAccount, Message, MessageSender, Shop
from app.services.instagram import InstagramClient, InstagramError, split_text
from app.services.responder import Responder
from app.services.webhook import MessagingEvent

logger = logging.getLogger(__name__)

# Instagram only allows replies within 24h of the customer's last message. Keep a margin so
# a slow job doesn't hit the boundary.
MESSAGING_WINDOW = timedelta(hours=24) - timedelta(minutes=5)
HISTORY_LIMIT = 20


async def handle_event(
    db: AsyncSession, event: MessagingEvent, queue: Queue, *, debounce_seconds: float
) -> None:
    account = await db.scalar(
        select(InstagramAccount).where(
            InstagramAccount.ig_user_id == event.account_ig_id,
            InstagramAccount.is_active.is_(True),
        )
    )
    if account is None:
        logger.info("webhook for unknown or inactive account %s", event.account_ig_id)
        return
    if await _message_exists(db, event.mid):
        return

    shop = await db.get(Shop, account.shop_id)
    assert shop is not None  # FK guarantees it
    conversation = await _get_or_create_conversation(db, shop.id, event.customer_igsid)

    if event.is_echo:
        await _record_echo(db, shop, conversation, event)
        return

    db.add(
        Message(
            conversation_id=conversation.id,
            sender=MessageSender.CUSTOMER,
            text=event.display_text,
            ig_message_id=event.mid,
        )
    )
    last = conversation.last_customer_message_at
    if last is None or event.timestamp > as_utc(last):
        conversation.last_customer_message_at = event.timestamp
    if not await _commit_ignoring_duplicate(db):
        return

    await queue.enqueue(
        "reply_conversation",
        str(conversation.id),
        event.timestamp.isoformat(),
        job_id=f"reply:{event.mid}",
        defer_seconds=debounce_seconds,
    )


async def _record_echo(
    db: AsyncSession, shop: Shop, conversation: Conversation, event: MessagingEvent
) -> None:
    # Our own reply whose echo arrived before the send call returned its mid: we store each
    # bot message *before* sending it, so match the in-flight one by text.
    pending = await db.scalars(
        select(Message).where(
            Message.conversation_id == conversation.id,
            Message.sender == MessageSender.BOT,
            Message.ig_message_id.is_(None),
        )
    )
    for message in pending:
        if message.text == event.text:
            message.ig_message_id = event.mid
            await _commit_ignoring_duplicate(db)
            return

    db.add(
        Message(
            conversation_id=conversation.id,
            sender=MessageSender.OWNER,
            text=event.display_text,
            ig_message_id=event.mid,
        )
    )
    if shop.handoff_pause_minutes > 0:
        conversation.bot_paused_until = utcnow() + timedelta(minutes=shop.handoff_pause_minutes)
    await _commit_ignoring_duplicate(db)


async def reply_to_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    trigger_at: datetime,
    instagram: InstagramClient,
    responder: Responder,
) -> None:
    """Answer the conversation, unless something newer or someone else already took over.

    Raises InstagramError when the failure is retryable, so the worker can retry the job.
    """
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.last_customer_message_at is None:
        return
    last_customer_at = as_utc(conversation.last_customer_message_at)
    if last_customer_at > trigger_at:
        return  # a newer message arrived; its own job will answer everything at once

    shop = await db.get(Shop, conversation.shop_id)
    account = await db.scalar(
        select(InstagramAccount).where(InstagramAccount.shop_id == conversation.shop_id)
    )
    if shop is None or not shop.bot_enabled or account is None or not account.is_active:
        return
    now = utcnow()
    if conversation.bot_paused_until and as_utc(conversation.bot_paused_until) > now:
        return
    if now - last_customer_at > MESSAGING_WINDOW:
        logger.info("conversation %s is outside the 24h window", conversation.id)
        return

    history = list(
        reversed(
            (
                await db.scalars(
                    select(Message)
                    .where(Message.conversation_id == conversation.id)
                    .order_by(Message.created_at.desc())
                    .limit(HISTORY_LIMIT)
                )
            ).all()
        )
    )
    if not history or history[-1].sender != MessageSender.CUSTOMER:
        return  # already answered, by us or by the owner

    reply = await responder.generate(shop, history)
    if reply is None or not reply.text.strip():
        return

    token = decrypt_secret(account.access_token_encrypted)
    for index, chunk in enumerate(split_text(reply.text)):
        message = Message(
            conversation_id=conversation.id,
            sender=MessageSender.BOT,
            text=chunk,
            unanswered=reply.unanswered,
            prompt_tokens=reply.prompt_tokens if index == 0 else None,
            completion_tokens=reply.completion_tokens if index == 0 else None,
        )
        db.add(message)
        await db.commit()
        try:
            mid = await instagram.send_text(token, conversation.customer_igsid, chunk)
        except InstagramError as exc:
            await db.delete(message)
            await db.commit()
            if exc.token_invalid:
                account.is_active = False
                await db.commit()
                logger.warning("instagram token revoked for shop %s", shop.id)
                return
            if exc.retryable:
                raise
            logger.warning("send failed for conversation %s: %s", conversation.id, exc)
            return
        message.ig_message_id = mid
        await db.commit()


async def _message_exists(db: AsyncSession, mid: str) -> bool:
    return await db.scalar(select(Message.id).where(Message.ig_message_id == mid)) is not None


async def _get_or_create_conversation(
    db: AsyncSession, shop_id: uuid.UUID, customer_igsid: str
) -> Conversation:
    query = select(Conversation).where(
        Conversation.shop_id == shop_id, Conversation.customer_igsid == customer_igsid
    )
    conversation = await db.scalar(query)
    if conversation is not None:
        return conversation
    conversation = Conversation(shop_id=shop_id, customer_igsid=customer_igsid)
    db.add(conversation)
    try:
        await db.commit()
    except IntegrityError:  # created concurrently by another job
        await db.rollback()
        conversation = await db.scalar(query)
        assert conversation is not None
    return conversation


async def _commit_ignoring_duplicate(db: AsyncSession) -> bool:
    """Commit; False if a concurrent job already stored the same message id."""
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return False
    return True
