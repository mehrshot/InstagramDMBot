import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk, str_enum


class ProposalStatus(enum.StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    DISCARDED = "discarded"


class TeachProposal(UUIDPk, Timestamps, Base):
    """What the AI understood from something the owner taught it, waiting for their OK.

    The owner can teach Javab in any form (typed text, a voice note, a Google Doc link, a
    file, a channel post); all of them become a proposal of product and knowledge changes
    that the owner confirms in the panel or with a button in Telegram.
    """

    __tablename__ = "teach_proposals"

    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), index=True
    )
    # text | voice | url | file | telegram_post | photo
    source: Mapped[str] = mapped_column(String(32))
    # Short description of the input for the owner ("صوت ۴۲ ثانیه‌ای", the link, file name).
    source_label: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[ProposalStatus] = mapped_column(
        str_enum(ProposalStatus), default=ProposalStatus.PENDING
    )
    summary: Mapped[str] = mapped_column(Text, default="")
    # {"products": [...], "knowledge": [...], "questions": [...]}; see services/teach.py.
    changes: Mapped[dict[str, Any]] = mapped_column(default=dict)
    # Telegram post the proposal came from, so the created product can link to it.
    telegram_post_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("telegram_posts.id", ondelete="SET NULL")
    )
    # Photo for the product(s) in this proposal (a photo the owner sent with a caption).
    image_url: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column()
    # What applying did, for the owner ("۳ محصول اضافه شد").
    result: Mapped[str | None] = mapped_column(Text)
