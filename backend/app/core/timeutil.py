from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(dt: datetime) -> datetime:
    """Some drivers (SQLite) return naive datetimes; all our stored times are UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
