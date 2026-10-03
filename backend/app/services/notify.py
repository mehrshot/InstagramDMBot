"""Alerts to the shop owner in Telegram or Bale, through the shared Javab bot of that app.

The owner links their Telegram/Bale account once (panel > Telegram > link). From then on the bot
tells them when a customer is waiting for a person, when the wallet runs low, and when a new
product was read from their channel, with buttons to act right there.
"""

import logging
import uuid
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_secret
from app.models import Channel, Conversation, Shop, TelegramAdmin, TelegramBot
from app.services import billing
from app.services.telegram import MAX_TEXT_LENGTH, TelegramClient, TelegramError

logger = logging.getLogger(__name__)

CHANNEL_LABELS = {Channel.INSTAGRAM: "اینستاگرام", Channel.TELEGRAM: "تلگرام", Channel.BALE: "بله"}


def channel_label(conversation: Conversation) -> str:
    label = CHANNEL_LABELS.get(conversation.channel, conversation.channel.value)
    if conversation.channel == Channel.TELEGRAM and conversation.channel_ref.startswith("biz:"):
        label += " (اکانت شخصی شما)"
    return label


def customer_label(conversation: Conversation) -> str:
    if conversation.customer_name and conversation.customer_username:
        return f"{conversation.customer_name} (@{conversation.customer_username})"
    if conversation.customer_username:
        return f"@{conversation.customer_username}"
    return conversation.customer_name or "مشتری"


def inline_keyboard(rows: list[list[tuple[str, str]]]) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": text, "callback_data": data} for text, data in row] for row in rows
        ]
    }


def handoff_keyboard(conversation_id: uuid.UUID) -> dict[str, Any]:
    return inline_keyboard(
        [
            [("✍️ جواب می‌دهم", f"reply:{conversation_id}")],
            [("✅ حل شد", f"resolve:{conversation_id}"), ("⏸ ساکت شو", f"pause:{conversation_id}")],
        ]
    )


class Notifier(Protocol):
    async def handoff(self, shop: Shop, conversation: Conversation) -> None: ...

    async def wallet_low(self, shop: Shop) -> None: ...

    async def wallet_empty(self, shop: Shop) -> None: ...

    async def message(
        self, shop: Shop, text: str, keyboard: dict[str, Any] | None = None
    ) -> None: ...


class NullNotifier:
    async def handoff(self, shop: Shop, conversation: Conversation) -> None:
        return None

    async def wallet_low(self, shop: Shop) -> None:
        return None

    async def wallet_empty(self, shop: Shop) -> None:
        return None

    async def message(self, shop: Shop, text: str, keyboard: dict[str, Any] | None = None) -> None:
        return None


class TelegramNotifier:
    def __init__(self, db: AsyncSession, client: TelegramClient) -> None:
        self._db = db
        self._client = client

    async def handoff(self, shop: Shop, conversation: Conversation) -> None:
        question = (conversation.handoff_question or "").strip()
        lines = [
            "🔔 یک مشتری منتظر جواب شماست",
            f"کانال: {channel_label(conversation)}",
            f"مشتری: {customer_label(conversation)}",
        ]
        if conversation.handoff_reason:
            lines.append(f"موضوع: {conversation.handoff_reason}")
        if question:
            lines.append(f"\nپیام مشتری:\n{question[:1500]}")
        lines.append("\nبا «جواب می‌دهم» پیام بعدی‌تان همین‌جا برای مشتری فرستاده می‌شود.")
        await self.message(shop, "\n".join(lines), handoff_keyboard(conversation.id))

    async def wallet_low(self, shop: Shop) -> None:
        await self.message(
            shop,
            f"⚠️ موجودی کیف پول «جواب» کم شده است: {billing.toman(shop.balance_rial)}\n"
            "برای اینکه ربات بدون وقفه جواب بدهد، از پنل کیف پول را شارژ کنید.",
        )

    async def wallet_empty(self, shop: Shop) -> None:
        await self.message(
            shop,
            "⛔️ موجودی کیف پول «جواب» تمام شده و ربات فعلا به مشتری‌ها جواب نمی‌دهد. "
            "پیام‌ها به شما ارجاع می‌شوند. از پنل کیف پول را شارژ کنید.",
        )

    async def message(self, shop: Shop, text: str, keyboard: dict[str, Any] | None = None) -> None:
        admins = (
            await self._db.scalars(
                select(TelegramAdmin).where(
                    TelegramAdmin.shop_id == shop.id, TelegramAdmin.notify.is_(True)
                )
            )
        ).all()
        bots: dict[str, TelegramBot | None] = {}
        for admin in admins:
            if admin.platform not in bots:
                bots[admin.platform] = await shared_bot(self._db, admin.platform)
            bot = bots[admin.platform]
            if bot is None:
                continue
            token = decrypt_secret(bot.token_encrypted)
            try:
                await self._client.for_platform(bot.platform).send_message(
                    token,
                    admin.telegram_user_id,
                    text[:MAX_TEXT_LENGTH],
                    reply_markup=keyboard,
                    disable_preview=True,
                )
            except TelegramError as exc:
                if exc.blocked:
                    # The owner blocked the bot: stop trying until they link again.
                    admin.notify = False
                    await self._db.commit()
                logger.info("could not notify shop %s admin: %s", shop.id, exc)


async def shared_bot(db: AsyncSession, platform: str = "telegram") -> TelegramBot | None:
    """The shared Javab bot of `platform` ("telegram" or "bale"), if the server runs one."""
    return await db.scalar(
        select(TelegramBot).where(
            TelegramBot.shop_id.is_(None),
            TelegramBot.platform == platform,
            TelegramBot.is_active.is_(True),
        )
    )
