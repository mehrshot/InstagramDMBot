import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPk, str_enum


class KnowledgeSection(enum.StrEnum):
    ABOUT = "about"
    SHIPPING = "shipping"
    PAYMENT = "payment"
    RETURNS = "returns"
    CONTACT = "contact"
    FAQ = "faq"
    FREE_TEXT = "free_text"
    FILE = "file"


class KnowledgeEntry(UUIDPk, Timestamps, Base):
    """A piece of static shop knowledge (shipping policy, an FAQ pair, extracted file text...)."""

    __tablename__ = "knowledge_entries"

    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), index=True
    )
    section: Mapped[KnowledgeSection] = mapped_column(str_enum(KnowledgeSection))
    title: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text)
    source_filename: Mapped[str | None] = mapped_column(String(255))


class ProductSourceKind(enum.StrEnum):
    GOOGLE_SHEET = "google_sheet"
    UPLOAD = "upload"


class ProductSource(UUIDPk, Timestamps, Base):
    """Where a shop's product/stock table comes from. Google Sheets are re-synced periodically."""

    __tablename__ = "product_sources"

    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), unique=True
    )
    kind: Mapped[ProductSourceKind] = mapped_column(str_enum(ProductSourceKind))
    url: Mapped[str | None] = mapped_column(Text)
    # Maps our canonical fields (name, color, size, price, stock...) to the sheet's column headers.
    column_mapping: Mapped[dict[str, Any]] = mapped_column(default=dict)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class Product(UUIDPk, Timestamps, Base):
    """One sellable variant: a row per product × colour × size combination."""

    __tablename__ = "products"
    __table_args__ = (Index("ix_products_shop_name", "shop_id", "name"),)

    shop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shops.id", ondelete="CASCADE"), index=True
    )
    sku: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(120))
    color: Mapped[str | None] = mapped_column(String(64))
    size: Mapped[str | None] = mapped_column(String(64))
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 0))  # Toman, no decimals
    stock: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    # Any extra sheet columns we don't model explicitly, kept so the bot can still use them.
    extra: Mapped[dict[str, Any]] = mapped_column(default=dict)
