"""Client for the Instagram API with Instagram Login (graph.instagram.com).

Every call Meta makes us do lives here, so the rest of the app never builds Meta URLs itself.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import Settings, get_settings
from app.core.timeutil import utcnow

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
GRAPH_URL = "https://graph.instagram.com"
SCOPES = ("instagram_business_basic", "instagram_business_manage_messages")

# Instagram rejects DM text longer than this.
MAX_TEXT_LENGTH = 1000
_LONG_LIVED_DEFAULT = timedelta(days=60)

# Graph API error codes worth retrying: unknown/service errors and rate limits.
_RETRYABLE_CODES = {1, 2, 4, 17, 32, 613}
_INVALID_TOKEN_CODE = 190


class InstagramError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        code: int | None = None,
        subcode: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.subcode = subcode

    @property
    def token_invalid(self) -> bool:
        """The token was revoked or expired; the owner has to reconnect."""
        return self.code == _INVALID_TOKEN_CODE

    @property
    def retryable(self) -> bool:
        if self.token_invalid:
            return False
        return self.status is None or self.status >= 500 or self.code in _RETRYABLE_CODES


@dataclass(frozen=True)
class LongLivedToken:
    access_token: str
    expires_at: datetime


@dataclass(frozen=True)
class Profile:
    # The professional account ID; webhook `entry.id` carries this same value.
    ig_user_id: str
    username: str


def split_text(text: str, limit: int = MAX_TEXT_LENGTH) -> list[str]:
    """Split a reply into DM-sized chunks, preferring paragraph, line, then word boundaries."""
    text = text.strip()
    chunks: list[str] = []
    while len(text) > limit:
        window = text[:limit]
        cut = max(window.rfind("\n\n"), window.rfind("\n"))
        if cut < limit // 2:
            cut = window.rfind(" ")
        if cut < limit // 2:
            cut = limit
        chunks.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        chunks.append(text)
    return chunks


class InstagramClient:
    def __init__(self, http: httpx.AsyncClient, settings: Settings | None = None) -> None:
        self._http = http
        self._settings = settings or get_settings()

    @property
    def redirect_uri(self) -> str:
        return f"{self._settings.public_base_url.rstrip('/')}/api/v1/instagram/callback"

    @property
    def _graph(self) -> str:
        return f"{GRAPH_URL}/{self._settings.meta_graph_api_version}"

    def authorize_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": self._settings.meta_app_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": ",".join(SCOPES),
                "state": state,
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def exchange_code(self, code: str) -> str:
        """Trade the OAuth code for a short-lived (1 hour) token."""
        data = await self._request(
            "POST",
            TOKEN_URL,
            data={
                "client_id": self._settings.meta_app_id,
                "client_secret": self._settings.meta_app_secret,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
                "code": code,
            },
        )
        # Meta has returned both {"data": [{...}]} and a flat object for this endpoint.
        item = data["data"][0] if isinstance(data.get("data"), list) else data
        return item["access_token"]

    async def get_long_lived_token(self, short_lived_token: str) -> LongLivedToken:
        data = await self._request(
            "GET",
            f"{GRAPH_URL}/access_token",
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": self._settings.meta_app_secret,
                "access_token": short_lived_token,
            },
        )
        return self._long_lived(data)

    async def refresh_token(self, token: str) -> LongLivedToken:
        """Extend a long-lived token by another 60 days (token must be at least 24h old)."""
        data = await self._request(
            "GET",
            f"{GRAPH_URL}/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": token},
        )
        return self._long_lived(data)

    async def get_profile(self, token: str) -> Profile:
        data = await self._request(
            "GET",
            f"{self._graph}/me",
            params={"fields": "user_id,username", "access_token": token},
        )
        return Profile(ig_user_id=str(data["user_id"]), username=data.get("username", ""))

    async def subscribe_webhooks(self, token: str) -> None:
        """Ask Meta to deliver this account's DMs to our webhook."""
        await self._request(
            "POST",
            f"{self._graph}/me/subscribed_apps",
            params={"subscribed_fields": "messages", "access_token": token},
        )

    async def get_customer_username(self, token: str, igsid: str) -> str | None:
        """Username of a customer who messaged the page (Instagram User Profile API)."""
        if self._settings.instagram_dry_run:
            return None
        data = await self._request(
            "GET", f"{self._graph}/{igsid}", params={"fields": "username", "access_token": token}
        )
        return data.get("username")

    async def list_media(self, token: str, limit: int = 200) -> list[dict[str, Any]]:
        """The account's own posts, newest first (id, caption, permalink, media, timestamp)."""
        if self._settings.instagram_dry_run:
            return []
        url: str | None = f"{self._graph}/me/media"
        params: dict[str, Any] | None = {
            "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp",
            "limit": 50,
            "access_token": token,
        }
        media: list[dict[str, Any]] = []
        while url and len(media) < limit:
            data = await self._request("GET", url, params=params)
            media.extend(data.get("data") or [])
            # The `next` URL already carries every parameter, including the token.
            url = (data.get("paging") or {}).get("next")
            params = None
        return media[:limit]

    async def send_post(self, token: str, recipient_igsid: str, media_id: str) -> str:
        """Share one of the account's own posts as a native post card; returns the mid."""
        if self._settings.instagram_dry_run:
            logger.info("DRY RUN: post %s to %s", media_id, recipient_igsid)
            return f"dry-run-{uuid.uuid4().hex}"
        data = await self._request(
            "POST",
            f"{self._graph}/me/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "recipient": {"id": recipient_igsid},
                "message": {"attachment": {"type": "MEDIA_SHARE", "payload": {"id": media_id}}},
            },
        )
        return data["message_id"]

    async def send_text(self, token: str, recipient_igsid: str, text: str) -> str:
        """Send one DM; returns Meta's message id. `text` must already fit MAX_TEXT_LENGTH."""
        if self._settings.instagram_dry_run:
            logger.info("DRY RUN: DM to %s: %s", recipient_igsid, text)
            return f"dry-run-{uuid.uuid4().hex}"
        data = await self._request(
            "POST",
            f"{self._graph}/me/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"recipient": {"id": recipient_igsid}, "message": {"text": text}},
        )
        return data["message_id"]

    @staticmethod
    def _long_lived(data: dict[str, Any]) -> LongLivedToken:
        expires_in = data.get("expires_in")
        lifetime = timedelta(seconds=int(expires_in)) if expires_in else _LONG_LIVED_DEFAULT
        return LongLivedToken(access_token=data["access_token"], expires_at=utcnow() + lifetime)

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            resp = await self._http.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            # Only the exception type: the message may contain the URL, which carries tokens.
            raise InstagramError(f"network error: {type(exc).__name__}") from None
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        if resp.is_error or "error" in data:
            raise _error_from(resp.status_code, data)
        return data


def _error_from(status: int, data: dict[str, Any]) -> InstagramError:
    err = data.get("error")
    if isinstance(err, dict):
        return InstagramError(
            err.get("message", "unknown error"),
            status=status,
            code=err.get("code"),
            subcode=err.get("error_subcode"),
        )
    # The OAuth endpoint uses a flat shape: {"error_type", "code", "error_message"}.
    return InstagramError(
        data.get("error_message") or f"HTTP {status}", status=status, code=data.get("code")
    )
