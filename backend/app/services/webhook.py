"""Parsing and verification of Instagram messaging webhooks."""

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


def verify_signature(body: bytes, signature_header: str | None, app_secret: str) -> bool:
    """Check Meta's `X-Hub-Signature-256: sha256=<hex>` HMAC of the raw request body."""
    if not app_secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.removeprefix("sha256="))


@dataclass(frozen=True)
class MessagingEvent:
    account_ig_id: str  # the shop's Instagram account (webhook entry.id)
    customer_igsid: str  # the other side of the conversation
    mid: str
    text: str
    # True when the message was sent *by* the shop's account (by the owner or by us).
    is_echo: bool
    timestamp: datetime
    attachment_types: tuple[str, ...] = ()

    @property
    def display_text(self) -> str:
        """Text as stored in history; non-text content becomes a marker like `[image]`."""
        markers = " ".join(f"[{t}]" for t in self.attachment_types)
        return " ".join(p for p in (self.text, markers) if p)


def parse_messaging_events(payload: dict[str, Any]) -> list[MessagingEvent]:
    """Extract message events; reactions, reads, deletions and unsupported types are dropped."""
    if payload.get("object") != "instagram":
        return []
    events: list[MessagingEvent] = []
    for entry in payload.get("entry") or []:
        account_id = str(entry.get("id", ""))
        for item in entry.get("messaging") or []:
            message = item.get("message")
            if not isinstance(message, dict) or not message.get("mid"):
                continue
            if message.get("is_deleted") or message.get("is_unsupported"):
                continue
            is_echo = bool(message.get("is_echo"))
            party = item.get("recipient") if is_echo else item.get("sender")
            customer_id = str((party or {}).get("id", ""))
            if not account_id or not customer_id or customer_id == account_id:
                continue
            timestamp_ms = item.get("timestamp")
            timestamp = (
                datetime.fromtimestamp(timestamp_ms / 1000, UTC)
                if isinstance(timestamp_ms, int | float)
                else datetime.now(UTC)
            )
            events.append(
                MessagingEvent(
                    account_ig_id=account_id,
                    customer_igsid=customer_id,
                    mid=message["mid"],
                    text=message.get("text") or "",
                    is_echo=is_echo,
                    timestamp=timestamp,
                    attachment_types=tuple(
                        str(a.get("type", "attachment")) for a in message.get("attachments") or []
                    )
                    + (("story_reply",) if (message.get("reply_to") or {}).get("story") else ()),
                )
            )
    return events
