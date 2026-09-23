import enum
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk, str_enum


class HandoffResolution(enum.StrEnum):
    OWNER_REPLY = "owner_reply"  # the owner answered the customer on Instagram
    MANUAL = "manual"  # the owner closed it from the panel


class Conversation(UUIDPk, Timestamps, Base):
    """A DM thread between a shop's page and one Instagram customer."""

    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("shop_id", "customer_igsid"),)

    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), index=True
    )
    # Instagram-scoped ID of the customer (IGSID); stable per page.
    customer_igsid: Mapped[str] = mapped_column(String(64))
    # None: not looked up yet; "": lookup failed (don't retry on every message).
    customer_username: Mapped[str | None] = mapped_column(String(64))
    last_customer_message_at: Mapped[datetime | None] = mapped_column()
    # Set when the owner replies by hand; the bot stays silent until then.
    bot_paused_until: Mapped[datetime | None] = mapped_column()

    # Handoff to the shop owner: the bot couldn't answer and the customer is waiting for a
    # person. Open while handoff_at is set and handoff_resolved_at is not. It resolves itself
    # when the owner replies on Instagram, or the owner closes it in the panel.
    handoff_at: Mapped[datetime | None] = mapped_column(index=True)
    handoff_reason: Mapped[str | None] = mapped_column(String(255))
    # What the customer asked, as shown to the owner.
    handoff_question: Mapped[str | None] = mapped_column(Text)
    handoff_resolved_at: Mapped[datetime | None] = mapped_column()
    handoff_resolved_by: Mapped[HandoffResolution | None] = mapped_column(
        str_enum(HandoffResolution)
    )

    @property
    def handoff_open(self) -> bool:
        return self.handoff_at is not None and self.handoff_resolved_at is None


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
    # The owner dismissed it from the "unanswered questions" list (usually after adding the
    # missing information to the knowledge base).
    unanswered_resolved: Mapped[bool] = mapped_column(default=False, server_default="0")
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
