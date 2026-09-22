import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk, str_enum


class Conversation(UUIDPk, Timestamps, Base):
    """A DM thread between a shop's page and one Instagram customer."""

    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("shop_id", "customer_igsid"),)

    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), index=True
    )
    # Instagram-scoped ID of the customer (IGSID); stable per page.
    customer_igsid: Mapped[str] = mapped_column(String(64))
    customer_username: Mapped[str | None] = mapped_column(String(64))
    last_customer_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set when the owner replies by hand; the bot stays silent until then.
    bot_paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MessageSender(enum.StrEnum):
    CUSTOMER = "customer"
    BOT = "bot"
    OWNER = "owner"


class Message(UUIDPk, Timestamps, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    sender: Mapped[MessageSender] = mapped_column(str_enum(MessageSender))
    text: Mapped[str] = mapped_column(Text, default="")
    # Meta's message id (mid); unique so webhook retries don't create duplicates.
    ig_message_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    # True when the bot could not answer from the shop's data (feeds the "unanswered" list).
    unanswered: Mapped[bool] = mapped_column(default=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
