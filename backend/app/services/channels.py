"""The channel layer: how a reply reaches a customer on each messaging channel.

The bot (responder, products, handoffs, billing) doesn't know about channels. A conversation
records its channel and endpoint (`Conversation.channel` / `channel_ref`); `sender_for` turns
that into a `ChannelSender` that can send text and product posts there.

    Instagram account ─┐                     ┌─► InstagramSender (Graph API)
    shared/custom bot ─┼─► Conversation ─────┼─► TelegramSender (Telegram or Bale Bot API)
    Telegram Business ─┤                     ├─► TelegramSender (business_connection_id)
    website widget ────┘                     └─► WebSender (stored; the widget reads it)
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.models import (
    Channel,
    Conversation,
    InstagramAccount,
    Plan,
    Shop,
    TelegramBot,
    TelegramBusinessConnection,
)
from app.services import instagram as ig
from app.services import telegram as tg
from app.services.instagram import InstagramClient, InstagramError
from app.services.posts import PostLink
from app.services.telegram import TelegramClient, TelegramError

logger = logging.getLogger(__name__)

# Instagram (and Telegram Business) only allow replies within 24h of the customer's last
# message. Keep a margin so a slow job doesn't hit the boundary.
_REPLY_WINDOW = timedelta(hours=24) - timedelta(minutes=5)

# Plans that may use each Telegram endpoint kind.
PLANS_FOR_CUSTOM_BOT = {Plan.PRO, Plan.BUSINESS}
PLANS_FOR_BUSINESS = {Plan.BUSINESS}


class SendError(Exception):
    """A channel refused or failed a send, in channel-independent terms."""

    def __init__(
        self, original: Exception, *, retryable: bool, endpoint_dead: bool = False
    ) -> None:
        super().__init__(str(original))
        # The channel's own error (InstagramError, TelegramError); re-raised for retries so
        # the worker's retry policy sees the real cause.
        self.original = original
        self.retryable = retryable
        # The account/bot/connection no longer works (token revoked, bot removed); it has
        # been deactivated and the owner must reconnect it.
        self.endpoint_dead = endpoint_dead


class ChannelSender(Protocol):
    channel: Channel
    # Replies are only allowed this long after the customer's last message (None: always).
    reply_window: timedelta | None
    max_text_length: int

    async def send_text(self, text: str) -> str:
        """Send one chunk (already split to max_text_length); returns the external id."""
        ...

    async def send_post(self, post: PostLink) -> str: ...

    async def typing(self) -> None: ...


@dataclass
class Gateways:
    """API clients for the channels; a missing one means that channel can't send."""

    instagram: InstagramClient | None = None
    telegram: TelegramClient | None = None


class InstagramSender:
    channel = Channel.INSTAGRAM
    reply_window: timedelta | None = _REPLY_WINDOW
    max_text_length = ig.MAX_TEXT_LENGTH

    def __init__(
        self, db: AsyncSession, account: InstagramAccount, client: InstagramClient, customer: str
    ) -> None:
        self._db = db
        self._account = account
        self._client = client
        self._customer = customer
        self._token = decrypt_secret(account.access_token_encrypted)

    async def send_text(self, text: str) -> str:
        try:
            return await self._client.send_text(self._token, self._customer, text)
        except InstagramError as exc:
            raise await self._error(exc) from exc

    async def send_post(self, post: PostLink) -> str:
        try:
            if post.media_id:
                try:
                    return await self._client.send_post(self._token, self._customer, post.media_id)
                except InstagramError as exc:
                    if exc.token_invalid:
                        raise
                    # e.g. the post was deleted after our last sync: the link still helps.
            return await self._client.send_text(self._token, self._customer, post.permalink)
        except InstagramError as exc:
            raise await self._error(exc) from exc

    async def typing(self) -> None:
        return None

    async def _error(self, exc: InstagramError) -> SendError:
        if exc.token_invalid:
            self._account.is_active = False
            await self._db.commit()
            logger.warning("instagram token revoked for shop %s", self._account.shop_id)
        return SendError(exc, retryable=exc.retryable, endpoint_dead=exc.token_invalid)


class TelegramSender:
    channel = Channel.TELEGRAM
    max_text_length = tg.MAX_TEXT_LENGTH

    def __init__(
        self,
        db: AsyncSession,
        bot: TelegramBot,
        client: TelegramClient,
        chat_id: int,
        business: TelegramBusinessConnection | None = None,
    ) -> None:
        self._db = db
        self._bot = bot
        self._client = client.for_platform(bot.platform)
        self.channel = Channel.BALE if bot.platform == "bale" else Channel.TELEGRAM
        self._chat_id = chat_id
        self._business = business
        self._token = decrypt_secret(bot.token_encrypted)
        self.reply_window = _REPLY_WINDOW if business else None

    @property
    def _connection(self) -> str | None:
        return self._business.connection_id if self._business else None

    async def send_text(self, text: str) -> str:
        try:
            message_id = await self._client.send_message(
                self._token, self._chat_id, text, business_connection_id=self._connection
            )
        except TelegramError as exc:
            raise await self._error(exc) from exc
        return self.external_id(message_id)

    async def send_post(self, post: PostLink) -> str:
        try:
            message_id = await self._send_post(post)
        except TelegramError as exc:
            raise await self._error(exc) from exc
        return self.external_id(message_id)

    async def _send_post(self, post: PostLink) -> int:
        connection = self._connection
        same_bot = post.tg_bot_id == self._bot.id
        # copyMessage keeps the post's photos and caption, but has no business variant and
        # only works through the bot that is in the channel.
        if post.tg_chat_id and post.tg_message_id and same_bot and not connection:
            try:
                return await self._client.copy_message(
                    self._token, self._chat_id, post.tg_chat_id, post.tg_message_id
                )
            except TelegramError as exc:
                if exc.token_invalid or exc.blocked or exc.retryable:
                    raise
                # The post was deleted, or the bot left the channel: fall back below.
        photo = post.photo if (same_bot or not post.tg_chat_id) else None
        if photo:
            return await self._client.send_photo(
                self._token,
                self._chat_id,
                photo,
                post.caption[: tg.MAX_CAPTION_LENGTH],
                business_connection_id=connection,
            )
        link = post.permalink if post.permalink.startswith("http") else None
        if link is None:
            raise TelegramError("nothing to send for this post", status=400)
        return await self._client.send_message(
            self._token, self._chat_id, link, business_connection_id=connection
        )

    async def typing(self) -> None:
        try:
            await self._client.send_chat_action(
                self._token, self._chat_id, business_connection_id=self._connection
            )
        except TelegramError:
            pass  # purely cosmetic

    def external_id(self, message_id: int) -> str:
        return telegram_message_key(self.endpoint_ref, self._chat_id, message_id)

    @property
    def endpoint_ref(self) -> str:
        return business_ref(self._business) if self._business else bot_ref(self._bot)

    async def _error(self, exc: TelegramError) -> SendError:
        if exc.token_invalid:
            self._bot.is_active = False
            self._bot.last_error = "توکن ربات نامعتبر شده است. دوباره آن را ثبت کنید."
            await self._db.commit()
            logger.warning("telegram bot %s token revoked", self._bot.id)
        return SendError(exc, retryable=exc.retryable, endpoint_dead=exc.token_invalid)


def bot_ref(bot: TelegramBot) -> str:
    return f"bot:{bot.id}"


def business_ref(connection: TelegramBusinessConnection) -> str:
    return f"biz:{connection.id}"


def telegram_message_key(endpoint_ref: str, chat_id: int, message_id: int) -> str:
    """Telegram message ids are only unique per chat; make them globally unique."""
    return f"tg:{endpoint_ref}:{chat_id}:{message_id}"


def plan_allows(shop: Shop, conversation_ref: str, bot: TelegramBot | None = None) -> bool:
    if conversation_ref.startswith("biz:"):
        return shop.plan in PLANS_FOR_BUSINESS
    if bot is not None and not bot.is_shared:
        return shop.plan in PLANS_FOR_CUSTOM_BOT
    return True


class WebSender:
    """The website chat widget: nothing is pushed anywhere. Messages are stored like on any
    channel, and the widget shows them (it asks for new ones while it's open)."""

    channel = Channel.WEB
    reply_window = None
    max_text_length = 4000

    async def send_text(self, text: str) -> str:
        return f"web:{uuid.uuid4()}"

    async def send_post(self, post: PostLink) -> str:
        return f"web:{uuid.uuid4()}"

    async def typing(self) -> None:
        return None


async def sender_for(
    db: AsyncSession, shop: Shop, conversation: Conversation, gateways: Gateways
) -> ChannelSender | None:
    """The sender for this conversation, or None if its endpoint can't be used right now
    (disconnected, deactivated, channel switched off, or not included in the shop's plan)."""
    if conversation.channel == Channel.INSTAGRAM:
        if not get_settings().instagram_enabled or gateways.instagram is None:
            return None
        account = await db.scalar(
            select(InstagramAccount).where(InstagramAccount.shop_id == shop.id)
        )
        if account is None or not account.is_active:
            return None
        return InstagramSender(db, account, gateways.instagram, conversation.customer_id)

    if conversation.channel in (Channel.TELEGRAM, Channel.BALE):
        if gateways.telegram is None:
            return None
        kind, _, raw_id = conversation.channel_ref.partition(":")
        try:
            ref_id = uuid.UUID(raw_id)
        except ValueError:
            return None
        business = None
        if kind == "biz":
            business = await db.get(TelegramBusinessConnection, ref_id)
            if business is None or not business.is_enabled or not business.can_reply:
                return None
            bot = await db.get(TelegramBot, business.bot_id)
        elif kind == "bot":
            bot = await db.get(TelegramBot, ref_id)
        else:
            return None
        if bot is None or not bot.is_active or not shop.channel_enabled(bot.platform):
            return None
        if not plan_allows(shop, conversation.channel_ref, bot):
            logger.info("shop %s plan doesn't include %s", shop.id, conversation.channel_ref)
            return None
        return TelegramSender(db, bot, gateways.telegram, int(conversation.customer_id), business)

    if conversation.channel == Channel.WEB:
        return WebSender()

    return None


def split_text(text: str, limit: int) -> list[str]:
    return ig.split_text(text, limit)
