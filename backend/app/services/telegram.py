"""Client for the Telegram Bot API, and for Bale's (بله) Telegram-compatible copy of it.

Every Bot API call the app makes lives here. The token is part of the URL, so it is never
logged and network errors are reported by type only. A client talks to one platform; use
`for_platform` to get the client for a given bot.
"""

import logging
import random
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

Platform = Literal["telegram", "bale"]

# Telegram rejects messages longer than this (captions: 1024).
MAX_TEXT_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024

# Updates our webhook asks for. Business and channel updates are not sent unless listed.
ALLOWED_UPDATES = [
    "message",
    "edited_message",
    "callback_query",
    "my_chat_member",
    "channel_post",
    "edited_channel_post",
    "business_connection",
    "business_message",
]


class TelegramError(Exception):
    def __init__(self, message: str, *, status: int | None = None, retry_after: int | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after

    @property
    def token_invalid(self) -> bool:
        """The bot token was revoked (or the bot deleted): the owner has to set it again."""
        text = str(self).lower()
        if self.status == 401:
            return True
        # Telegram: 404 "Not Found" for a deleted bot; Bale: 403 "Token not found".
        return self.status in (403, 404) and ("token" in text or text.strip() == "not found")

    @property
    def blocked(self) -> bool:
        """The user blocked the bot or deleted their account; sending again won't help."""
        return self.status == 403 and not self.token_invalid

    @property
    def retryable(self) -> bool:
        return self.status is None or self.status == 429 or self.status >= 500


@dataclass(frozen=True)
class BotInfo:
    id: int
    username: str
    first_name: str
    # Whether Telegram Business owners can connect this bot to their account (BotFather
    # setting "Business Mode").
    can_connect_to_business: bool = False


class TelegramClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        settings: Settings | None = None,
        platform: Platform = "telegram",
    ) -> None:
        self._http = http
        self._settings = settings or get_settings()
        self.platform: Platform = platform

    def for_platform(self, platform: str) -> "TelegramClient":
        """The client for a bot of `platform` ("telegram" or "bale")."""
        if platform == self.platform:
            return self
        return TelegramClient(
            self._http, self._settings, "bale" if platform == "bale" else "telegram"
        )

    @property
    def base(self) -> str:
        if self.platform == "bale":
            return self._settings.bale_api_base.rstrip("/")
        return self._settings.telegram_api_base.rstrip("/")

    @property
    def dry_run(self) -> bool:
        return self._settings.telegram_dry_run

    async def get_me(self, token: str) -> BotInfo:
        data = await self._call(token, "getMe", {}, allow_dry_run=False)
        return BotInfo(
            id=int(data["id"]),
            username=str(data.get("username") or ""),
            first_name=str(data.get("first_name") or ""),
            can_connect_to_business=bool(data.get("can_connect_to_business")),
        )

    async def set_webhook(self, token: str, url: str, secret: str) -> None:
        if self.platform == "bale":
            # Bale takes only the URL (no secret header): the secret travels in the URL.
            await self._call(token, "setWebhook", {"url": f"{url}?secret={secret}"})
            return
        await self._call(
            token,
            "setWebhook",
            {
                "url": url,
                "secret_token": secret,
                "allowed_updates": ALLOWED_UPDATES,
                "drop_pending_updates": False,
            },
        )

    async def delete_webhook(self, token: str) -> None:
        await self._call(token, "deleteWebhook", {}, allow_dry_run=False)

    async def get_updates(
        self, token: str, offset: int, poll_seconds: int = 25
    ) -> list[dict[str, Any]]:
        """Long polling, for local development without a public webhook URL."""
        base = self.base
        try:
            resp = await self._http.post(
                f"{base}/bot{token}/getUpdates",
                json={
                    "offset": offset,
                    "timeout": poll_seconds,
                    "allowed_updates": ALLOWED_UPDATES,
                },
                timeout=poll_seconds + 10,
            )
        except httpx.HTTPError as exc:
            raise TelegramError(f"network error: {type(exc).__name__}") from None
        data = resp.json() if resp.content else {}
        if not data.get("ok"):
            raise TelegramError(str(data.get("description")), status=resp.status_code)
        return list(data.get("result") or [])

    async def send_message(
        self,
        token: str,
        chat_id: int | str,
        text: str,
        *,
        business_connection_id: str | None = None,
        reply_markup: dict[str, Any] | None = None,
        disable_preview: bool = False,
    ) -> int:
        """Send a text message; returns its message_id. `text` must fit MAX_TEXT_LENGTH."""
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if business_connection_id:
            payload["business_connection_id"] = business_connection_id
        if reply_markup:
            payload["reply_markup"] = reply_markup
        if disable_preview:
            payload["link_preview_options"] = {"is_disabled": True}
        data = await self._call(token, "sendMessage", payload)
        return int(data.get("message_id", 0))

    async def send_photo(
        self,
        token: str,
        chat_id: int | str,
        photo: str,
        caption: str = "",
        *,
        business_connection_id: str | None = None,
    ) -> int:
        """`photo` is a file_id this bot has seen, or a public https URL."""
        payload: dict[str, Any] = {"chat_id": chat_id, "photo": photo}
        if caption:
            payload["caption"] = caption[:MAX_CAPTION_LENGTH]
        if business_connection_id:
            payload["business_connection_id"] = business_connection_id
        data = await self._call(token, "sendPhoto", payload)
        return int(data.get("message_id", 0))

    async def copy_message(
        self, token: str, chat_id: int | str, from_chat_id: int, message_id: int
    ) -> int:
        """Re-send a post (e.g. from the shop's channel) without the "forwarded" header."""
        data = await self._call(
            token,
            "copyMessage",
            {"chat_id": chat_id, "from_chat_id": from_chat_id, "message_id": message_id},
        )
        return int(data.get("message_id", 0))

    async def send_chat_action(
        self, token: str, chat_id: int | str, *, business_connection_id: str | None = None
    ) -> None:
        payload: dict[str, Any] = {"chat_id": chat_id, "action": "typing"}
        if business_connection_id:
            payload["business_connection_id"] = business_connection_id
        await self._call(token, "sendChatAction", payload)

    async def answer_callback(self, token: str, callback_id: str, text: str = "") -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text[:200]
        await self._call(token, "answerCallbackQuery", payload)

    async def edit_reply_markup(
        self, token: str, chat_id: int, message_id: int, reply_markup: dict[str, Any] | None
    ) -> None:
        payload: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        await self._call(token, "editMessageReplyMarkup", payload)

    async def get_business_connection(self, token: str, connection_id: str) -> dict[str, Any]:
        return await self._call(
            token, "getBusinessConnection", {"business_connection_id": connection_id}
        )

    async def download_file(self, token: str, file_id: str, max_bytes: int) -> bytes:
        """Download a file the user sent (voice note, document, photo)."""
        info = await self._call(token, "getFile", {"file_id": file_id}, allow_dry_run=False)
        size = info.get("file_size")
        if isinstance(size, int) and size > max_bytes:
            raise TelegramError("file too large", status=413)
        path = info.get("file_path")
        if not path:
            raise TelegramError("file has no path", status=400)
        base = self.base
        try:
            resp = await self._http.get(f"{base}/file/bot{token}/{path}", timeout=60)
        except httpx.HTTPError as exc:
            raise TelegramError(f"network error: {type(exc).__name__}") from None
        if resp.is_error:
            raise TelegramError("download failed", status=resp.status_code)
        if len(resp.content) > max_bytes:
            raise TelegramError("file too large", status=413)
        return resp.content

    async def _call(
        self, token: str, method: str, payload: dict[str, Any], *, allow_dry_run: bool = True
    ) -> Any:
        if allow_dry_run and self.dry_run:
            logger.info("DRY RUN telegram %s: %s", method, _loggable(payload))
            return {"message_id": random.randint(10**6, 10**9)}
        base = self.base
        try:
            resp = await self._http.post(f"{base}/bot{token}/{method}", json=payload, timeout=30)
        except httpx.HTTPError as exc:
            raise TelegramError(f"network error: {type(exc).__name__}") from None
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        if resp.is_error or not data.get("ok"):
            params = data.get("parameters") or {}
            raise TelegramError(
                str(data.get("description") or f"HTTP {resp.status_code}"),
                status=int(data.get("error_code") or resp.status_code),
                retry_after=params.get("retry_after"),
            )
        return data.get("result")


def _loggable(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: (v[:200] if isinstance(v, str) else v) for k, v in payload.items()}
