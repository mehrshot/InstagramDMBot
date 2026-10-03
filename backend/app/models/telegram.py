"""Telegram (and Bale): bots, the owner's linked accounts, Business connections, channels.

Bale (بله) has a Telegram-compatible Bot API, so its bots live in the same tables with
`platform = "bale"`. Bale has no Business connections or channel-post updates.

Three ways a shop's customers reach the bot (all served by the same backend):
- shared bot: the one "Javab" bot; the shop's start link (?start=s_<slug>) tells it which shop
  the customer came for.
- custom bot: the shop's own bot (made in @BotFather); the token is stored encrypted here.
- business: the owner connects a bot to their own Telegram account (Telegram Business), and the
  bot answers the owner's private chats on their behalf.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk


class TelegramBot(UUIDPk, Timestamps, Base):
    __tablename__ = "telegram_bots"
    __table_args__ = (
        UniqueConstraint("platform", "bot_user_id", name="uq_telegram_bots_account"),
        UniqueConstraint("shop_id", "platform", name="uq_telegram_bots_shop_platform"),
    )

    # "telegram" or "bale".
    platform: Mapped[str] = mapped_column(String(16), default="telegram", server_default="telegram")
    # None for the shared Javab bot; otherwise the shop that owns this custom bot (a shop can
    # have one on Telegram and one on Bale).
    shop_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), index=True
    )
    token_encrypted: Mapped[str] = mapped_column(Text)
    bot_user_id: Mapped[int] = mapped_column(BigInteger)
    username: Mapped[str] = mapped_column(String(64))
    # Telegram echoes this in X-Telegram-Bot-Api-Secret-Token on every webhook call.
    webhook_secret: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_error: Mapped[str | None] = mapped_column(Text)

    @property
    def is_shared(self) -> bool:
        return self.shop_id is None


class TelegramAdmin(UUIDPk, Timestamps, Base):
    """A Telegram/Bale account linked to a shop: gets alerts and manages it from the bot."""

    __tablename__ = "telegram_admins"
    __table_args__ = (
        UniqueConstraint("platform", "telegram_user_id", name="uq_telegram_admins_account"),
    )

    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String(16), default="telegram", server_default="telegram")
    # One shop per account keeps the bot's admin menu unambiguous.
    telegram_user_id: Mapped[int] = mapped_column(BigInteger)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(128), default="")
    notify: Mapped[bool] = mapped_column(Boolean, default=True)


class TelegramBusinessConnection(UUIDPk, Timestamps, Base):
    __tablename__ = "telegram_business_connections"

    connection_id: Mapped[str] = mapped_column(String(128), unique=True)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), index=True
    )
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("telegram_bots.id", ondelete="CASCADE"))
    # The owner's Telegram account the bot answers for.
    telegram_user_id: Mapped[int] = mapped_column(BigInteger)
    user_chat_id: Mapped[int] = mapped_column(BigInteger)
    can_reply: Mapped[bool] = mapped_column(Boolean, default=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class TelegramChannel(UUIDPk, Timestamps, Base):
    """The shop's Telegram channel; our bot is an admin there and reads new product posts."""

    __tablename__ = "telegram_channels"
    __table_args__ = (UniqueConstraint("bot_id", "chat_id"),)

    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), index=True
    )
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("telegram_bots.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(255), default="")
    username: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class TelegramPost(UUIDPk, Timestamps, Base):
    """A post from the shop's channel (read live, or forwarded to the bot by the owner)."""

    __tablename__ = "telegram_posts"
    __table_args__ = (UniqueConstraint("chat_id", "message_id"),)

    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), index=True
    )
    # The bot that saw the post: file ids and copyMessage only work through that bot.
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("telegram_bots.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger)
    # Public channels have a username, which gives the post a t.me link.
    channel_username: Mapped[str | None] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text, default="")
    photo_file_id: Mapped[str | None] = mapped_column(String(255))
    media_group_id: Mapped[str | None] = mapped_column(String(64))
    posted_at: Mapped[datetime | None] = mapped_column()

    @property
    def public_url(self) -> str | None:
        if self.channel_username:
            return f"https://t.me/{self.channel_username}/{self.message_id}"
        return None


class TelegramSession(UUIDPk, Timestamps, Base):
    """What one Telegram user is doing with one of our bots."""

    __tablename__ = "telegram_sessions"
    __table_args__ = (UniqueConstraint("bot_id", "telegram_user_id"),)

    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("telegram_bots.id", ondelete="CASCADE"))
    telegram_user_id: Mapped[int] = mapped_column(BigInteger)
    # On the shared bot: the shop this customer came for (from the start link).
    shop_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shops.id", ondelete="CASCADE"))
    # "customer" or "admin" (a linked owner managing their shop).
    mode: Mapped[str] = mapped_column(String(16), default="customer")
    # Admin flow state, e.g. {"reply_to": "<conversation id>"}.
    state: Mapped[dict[str, Any]] = mapped_column(default=dict)
