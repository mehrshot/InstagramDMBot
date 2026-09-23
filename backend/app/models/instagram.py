import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPk

if TYPE_CHECKING:
    from app.models.user import Shop


class InstagramAccount(UUIDPk, Timestamps, Base):
    __tablename__ = "instagram_accounts"

    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), unique=True
    )
    # Instagram professional account ID; webhooks are routed to a shop by this value.
    ig_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64))
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column()
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    shop: Mapped["Shop"] = relationship(back_populates="instagram_account")
