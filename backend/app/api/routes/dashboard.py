"""Panel home: setup checklist, test chat, and usage numbers."""

from datetime import timedelta
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select

from app.api.deps import LLM, CurrentShop, DbSession
from app.core.config import get_settings
from app.core.timeutil import utcnow
from app.models import (
    Conversation,
    InstagramAccount,
    KnowledgeEntry,
    Message,
    MessageSender,
    Product,
    ProductSource,
)
from app.services.llm import LLMError
from app.services.responder import ChatTurn, LLMResponder, PlaceholderResponder

router = APIRouter(tags=["dashboard"])


class SetupStatus(BaseModel):
    instagram_connected: bool
    # False when Meta revoked access; the owner must reconnect.
    instagram_active: bool
    instagram_username: str | None
    knowledge_entries: int
    products_connected: bool
    product_count: int
    product_error: str | None
    # False until the server has an AI provider key; the bot then only sends the fallback.
    ai_ready: bool
    bot_enabled: bool


class Stats(BaseModel):
    conversations: int
    customer_messages: int
    bot_replies: int
    open_unanswered: int


class DashboardOut(BaseModel):
    setup: SetupStatus
    # DMs waiting for the owner right now (the bot didn't know the answer).
    open_handoffs: int
    last_7_days: Stats
    tokens_this_month: int


class PlaygroundTurn(BaseModel):
    role: Literal["customer", "bot"]
    text: str = Field(min_length=1, max_length=2000)


class PlaygroundIn(BaseModel):
    # The whole test conversation so far, oldest first, ending with the customer's message.
    messages: list[PlaygroundTurn] = Field(min_length=1, max_length=30)


class PostCard(BaseModel):
    permalink: str
    caption: str
    preview_url: str | None


class PlaygroundOut(BaseModel):
    reply: str
    # True means in a real DM the bot would hand this over to the owner.
    unanswered: bool
    handoff_reason: str | None
    # What the bot looked up in the product list (for "why did it say that?").
    product_lookups: list[dict[str, Any]]
    # Instagram posts sent right after the reply, as post cards.
    posts: list[PostCard] = []
    ai_ready: bool


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(shop: CurrentShop, db: DbSession) -> DashboardOut:
    account = await db.scalar(select(InstagramAccount).where(InstagramAccount.shop_id == shop.id))
    source = await db.scalar(select(ProductSource).where(ProductSource.shop_id == shop.id))
    knowledge_count = await db.scalar(
        select(func.count()).select_from(KnowledgeEntry).where(KnowledgeEntry.shop_id == shop.id)
    )
    product_count = await db.scalar(
        select(func.count()).select_from(Product).where(Product.shop_id == shop.id)
    )

    since = utcnow() - timedelta(days=7)
    shop_messages = (
        select(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.shop_id == shop.id)
    )

    async def count(query) -> int:
        return await db.scalar(select(func.count()).select_from(query.subquery())) or 0

    month_start = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    tokens = await db.scalar(
        select(
            func.coalesce(
                func.sum(
                    func.coalesce(Message.prompt_tokens, 0)
                    + func.coalesce(Message.completion_tokens, 0)
                ),
                0,
            )
        )
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.shop_id == shop.id, Message.created_at >= month_start)
    )

    open_handoffs = await db.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(
            Conversation.shop_id == shop.id,
            Conversation.handoff_at.is_not(None),
            Conversation.handoff_resolved_at.is_(None),
        )
    )

    return DashboardOut(
        open_handoffs=open_handoffs or 0,
        setup=SetupStatus(
            instagram_connected=account is not None,
            instagram_active=bool(account and account.is_active),
            instagram_username=account.username if account else None,
            knowledge_entries=knowledge_count or 0,
            products_connected=source is not None,
            product_count=product_count or 0,
            product_error=source.last_error if source else None,
            ai_ready=get_settings().llm_configured,
            bot_enabled=shop.bot_enabled,
        ),
        last_7_days=Stats(
            conversations=await count(
                select(Conversation).where(
                    Conversation.shop_id == shop.id,
                    Conversation.last_customer_message_at >= since,
                )
            ),
            customer_messages=await count(
                shop_messages.where(
                    Message.sender == MessageSender.CUSTOMER, Message.created_at >= since
                )
            ),
            bot_replies=await count(
                shop_messages.where(
                    Message.sender == MessageSender.BOT, Message.created_at >= since
                )
            ),
            open_unanswered=await count(
                shop_messages.where(
                    and_(Message.unanswered.is_(True), Message.unanswered_resolved.is_(False))
                )
            ),
        ),
        tokens_this_month=int(tokens or 0),
    )


@router.post("/playground/chat", response_model=PlaygroundOut)
async def playground_chat(
    body: PlaygroundIn, shop: CurrentShop, db: DbSession, llm: LLM
) -> PlaygroundOut:
    """Test the bot with the shop's current data, without Instagram. Nothing is saved.

    Works while the bot is switched off, so owners can try it before going live.
    """
    if body.messages[-1].role != "customer":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "آخرین پیام باید از طرف مشتری باشد"
        )
    history = [ChatTurn(sender=m.role, text=m.text) for m in body.messages]
    responder = LLMResponder(llm, db) if llm.configured else PlaceholderResponder()
    try:
        reply = await responder.generate(shop, history)
    except LLMError:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "سرویس هوش مصنوعی پاسخ نداد. چند لحظه بعد دوباره امتحان کنید.",
        ) from None
    if reply is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "پیامی برای پاسخ وجود ندارد")
    return PlaygroundOut(
        reply=reply.text,
        unanswered=reply.unanswered,
        handoff_reason=reply.handoff_reason,
        product_lookups=reply.tool_trace,
        posts=[
            PostCard(permalink=p.permalink, caption=p.caption[:300], preview_url=p.preview_url)
            for p in reply.posts
        ],
        ai_ready=llm.configured,
    )
