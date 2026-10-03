"""Registering bots with Telegram and Bale: the shared Javab bots and shops' own bots."""

import logging
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decrypt_secret, encrypt_secret
from app.models import Shop, TelegramBot
from app.services.channels import PLANS_FOR_CUSTOM_BOT
from app.services.telegram import TelegramClient, TelegramError

logger = logging.getLogger(__name__)

PLATFORMS = ("telegram", "bale")


class BotSetupError(Exception):
    """User-facing (Persian) reason a bot could not be connected."""


def webhook_url(bot_id: uuid.UUID) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/webhooks/telegram/{bot_id}"


def shared_token(platform: str) -> str:
    settings = get_settings()
    return settings.bale_bot_token if platform == "bale" else settings.telegram_bot_token


def bot_link(platform: str, username: str) -> str:
    """Public link of a bot: t.me for Telegram, ble.ir for Bale."""
    host = "ble.ir" if platform == "bale" else "t.me"
    return f"https://{host}/{username}"


async def ensure_shared_bot(
    db: AsyncSession,
    client: TelegramClient,
    *,
    platform: str = "telegram",
    set_webhook: bool = True,
) -> TelegramBot | None:
    """Create/refresh the shared bot from TELEGRAM_BOT_TOKEN (or BALE_BOT_TOKEN) and point
    its webhook here."""
    token = shared_token(platform)
    if not token:
        return None
    client = client.for_platform(platform)
    info = await client.get_me(token)
    bot = await db.scalar(
        select(TelegramBot).where(
            TelegramBot.platform == platform, TelegramBot.bot_user_id == info.id
        )
    )
    if bot is None:
        # A different token than before: retire the old shared bot of this platform.
        old_bots = await db.scalars(
            select(TelegramBot).where(
                TelegramBot.shop_id.is_(None), TelegramBot.platform == platform
            )
        )
        for old in old_bots:
            old.is_active = False
        bot = TelegramBot(
            platform=platform,
            shop_id=None,
            bot_user_id=info.id,
            webhook_secret=secrets.token_urlsafe(32),
            token_encrypted="",
        )
        db.add(bot)
    bot.username = info.username
    bot.token_encrypted = encrypt_secret(token)
    bot.is_active = True
    bot.last_error = None
    await db.commit()
    if set_webhook:
        await client.set_webhook(token, webhook_url(bot.id), bot.webhook_secret)
    logger.info("shared %s bot @%s ready", platform, bot.username)
    return bot


async def connect_custom_bot(
    db: AsyncSession,
    shop: Shop,
    token: str,
    client: TelegramClient,
    *,
    platform: str = "telegram",
    set_webhook: bool = True,
) -> TelegramBot:
    """Connect the shop's own bot (made in Telegram's @BotFather or Bale's) by its token."""
    if shop.plan not in PLANS_FOR_CUSTOM_BOT:
        raise BotSetupError("ربات اختصاصی در پلن «حرفه‌ای» و «بیزینس» فعال است.")
    token = token.strip()
    client = client.for_platform(platform)
    try:
        info = await client.get_me(token)
    except TelegramError as exc:
        if exc.retryable:
            raise BotSetupError("سرور پیام‌رسان در دسترس نبود؛ کمی بعد دوباره تلاش کنید.") from None
        raise BotSetupError("توکن ربات نامعتبر است. آن را دوباره از BotFather کپی کنید.") from None

    owner = await db.scalar(
        select(TelegramBot).where(
            TelegramBot.platform == platform, TelegramBot.bot_user_id == info.id
        )
    )
    if owner is not None and owner.shop_id != shop.id:
        raise BotSetupError("این ربات به فروشگاه دیگری وصل است.")
    bot = owner or await db.scalar(
        select(TelegramBot).where(TelegramBot.shop_id == shop.id, TelegramBot.platform == platform)
    )
    if bot is not None and (bot.bot_user_id != info.id or bot.platform != platform):
        await _drop_webhook(bot, client.for_platform(bot.platform))
    if bot is None:
        bot = TelegramBot(shop_id=shop.id, webhook_secret=secrets.token_urlsafe(32))
        db.add(bot)
    bot.platform = platform
    bot.bot_user_id = info.id
    bot.username = info.username
    bot.token_encrypted = encrypt_secret(token)
    bot.is_active = True
    bot.last_error = None
    await db.commit()
    if set_webhook:
        try:
            await client.set_webhook(token, webhook_url(bot.id), bot.webhook_secret)
        except TelegramError as exc:
            bot.last_error = "ثبت وبهوک ناموفق بود؛ دوباره تلاش کنید."
            await db.commit()
            raise BotSetupError(f"ثبت وبهوک ربات ناموفق بود: {exc}") from None
    return bot


async def disconnect_custom_bot(
    db: AsyncSession, shop: Shop, client: TelegramClient, platform: str = "telegram"
) -> None:
    bot = await db.scalar(
        select(TelegramBot).where(TelegramBot.shop_id == shop.id, TelegramBot.platform == platform)
    )
    if bot is None:
        return
    await _drop_webhook(bot, client.for_platform(bot.platform))
    bot.is_active = False
    await db.commit()


async def _drop_webhook(bot: TelegramBot, client: TelegramClient) -> None:
    try:
        await client.delete_webhook(decrypt_secret(bot.token_encrypted))
    except (TelegramError, RuntimeError) as exc:
        logger.info("could not delete webhook of bot %s: %s", bot.id, exc)
