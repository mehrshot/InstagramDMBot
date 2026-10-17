import enum
import secrets
import string
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPk, str_enum

if TYPE_CHECKING:
    from app.models.instagram import InstagramAccount

_SLUG_ALPHABET = string.ascii_lowercase + string.digits


def new_slug() -> str:
    """Short public id of a shop, used in its Telegram start link (t.me/<bot>?start=s_<slug>)."""
    return "".join(secrets.choice(_SLUG_ALPHABET) for _ in range(8))


class Plan(enum.StrEnum):
    """What a shop pays for on top of usage. Usage (AI answers) costs the same on every plan."""

    BASIC = "basic"  # the shared Javab bot with the shop's own start link (+ Instagram)
    PRO = "pro"  # + the shop's own Telegram bot
    BUSINESS = "business"  # + Javab answers inside the owner's own Telegram account


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set when the owner opened the link we emailed them.
    email_verified_at: Mapped[datetime | None] = mapped_column()
    # A verified mobile number (+98912...), by an SMS code or by sharing the contact of their
    # Telegram/Bale account with our bot. One number belongs to one account.
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    phone_verified_at: Mapped[datetime | None] = mapped_column()
    # The SMS code waiting to be typed in: the number it went to, its hash and lifetime.
    phone_pending: Mapped[str | None] = mapped_column(String(20))
    phone_code_hash: Mapped[str | None] = mapped_column(String(64))
    phone_code_expires_at: Mapped[datetime | None] = mapped_column()
    phone_code_attempts: Mapped[int] = mapped_column(default=0, server_default="0")

    shop: Mapped["Shop"] = relationship(back_populates="owner", uselist=False)


class Shop(UUIDPk, Timestamps, Base):
    """The tenant. Everything the bot knows and does is scoped to a shop."""

    __tablename__ = "shops"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(32), unique=True, default=new_slug)

    # Bot behaviour settings
    bot_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    tone: Mapped[str] = mapped_column(String(16), default="friendly")  # friendly | formal
    use_emoji: Mapped[bool] = mapped_column(Boolean, default=True)
    fallback_message: Mapped[str] = mapped_column(
        Text, default="سوالتون رو ثبت کردم، همکارم به زودی جواب میده 🙏"
    )
    forbidden_rules: Mapped[str] = mapped_column(Text, default="")
    # How long the bot stays silent in a thread after the owner replies manually.
    handoff_pause_minutes: Mapped[int] = mapped_column(default=120)

    # The owner's time zone (IANA name); the panel keeps it in sync. Used to read the page's
    # insights in local time (best hours to post).
    timezone: Mapped[str] = mapped_column(
        String(40), default="Asia/Tehran", server_default="Asia/Tehran"
    )

    # Comments on the shop's posts and reels: "off", "public" (reply under the comment),
    # "private" (answer in a DM) or "both" (the answer in a DM and a short public note).
    comment_mode: Mapped[str] = mapped_column(String(8), default="both", server_default="both")
    # Thank people for compliments ("عالیه 😍") with a short public reply.
    comment_thank_praise: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    # Hide comments the bot recognises as spam (they stay visible to their author).
    comment_hide_spam: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    # Billing: a prepaid wallet in rial. Every AI answer is deducted from it.
    plan: Mapped[Plan] = mapped_column(
        str_enum(Plan), default=Plan.BASIC, server_default=Plan.BASIC.value
    )
    plan_renews_at: Mapped[datetime | None] = mapped_column()
    # A downgrade the owner asked for; applied when the paid month ends.
    plan_next: Mapped[Plan | None] = mapped_column(str_enum(Plan))
    balance_rial: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    # When we last told the owner the wallet is low / empty (so we don't repeat it).
    low_balance_notified_at: Mapped[datetime | None] = mapped_column()
    empty_wallet_notified_at: Mapped[datetime | None] = mapped_column()
    # The sign-up gift is given once, after the owner links their Telegram/Bale account
    # (and verifies their phone); see services/gifts.py.
    signup_gift_at: Mapped[datetime | None] = mapped_column()

    # Telegram: customers reach the shop through the shared bot with this shop's start link.
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    # Bale is a separate channel with its own switch (a shop may use one and not the other).
    bale_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    # One-time code for linking the owner's Telegram account (t.me/<bot>?start=a_<code>).
    telegram_link_code: Mapped[str | None] = mapped_column(String(64), unique=True)
    telegram_link_expires_at: Mapped[datetime | None] = mapped_column()

    def channel_enabled(self, platform: str) -> bool:
        return self.bale_enabled if platform == "bale" else self.telegram_enabled

    owner: Mapped[User] = relationship(back_populates="shop")
    instagram_account: Mapped["InstagramAccount | None"] = relationship(
        back_populates="shop", uselist=False
    )
