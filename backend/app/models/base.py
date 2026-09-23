import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Dialect, Enum, MetaData, TypeDecorator, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.timeutil import utcnow

# Deterministic constraint names keep Alembic migrations stable across databases.
_NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class UTCDateTime(TypeDecorator[datetime]):
    """Always stores UTC and always returns timezone-aware UTC datetimes.

    Postgres does this natively; SQLite (local development) drops the offset, which would make
    the API emit times without "Z" and the panel show them in the browser's local time.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(UTC)
        return value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=_NAMING)
    type_annotation_map = {dict[str, Any]: JSON, datetime: UTCDateTime}


class UUIDPk:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class Timestamps:
    # Python-side defaults give microsecond precision on every DB, so ordering by
    # created_at (e.g. message history) is stable.
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow, server_default=func.now(), onupdate=utcnow
    )


def str_enum(enum_cls: type[enum.StrEnum]) -> Enum:
    """Store enums as plain strings (by value) instead of native DB enum types."""
    return Enum(
        enum_cls,
        native_enum=False,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )
