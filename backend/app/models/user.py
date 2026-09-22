import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPk

if TYPE_CHECKING:
    from app.models.instagram import InstagramAccount


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    shop: Mapped["Shop"] = relationship(back_populates="owner", uselist=False)


class Shop(UUIDPk, Timestamps, Base):
    """The tenant. Everything the bot knows and does is scoped to a shop."""

    __tablename__ = "shops"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    name: Mapped[str] = mapped_column(String(120))

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

    owner: Mapped[User] = relationship(back_populates="shop")
    instagram_account: Mapped["InstagramAccount | None"] = relationship(
        back_populates="shop", uselist=False
    )
