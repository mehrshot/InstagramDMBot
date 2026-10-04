"""Telling the team (and owners) about things that happen: sign-ups, payments.

Team messages go through the shared Telegram bot to OPS_TELEGRAM_CHAT_ID (a team group), or,
without one, to each OPS_ADMIN_TELEGRAM_IDS member. Failures are logged, never raised: an
announcement must not break the request that triggered it.
"""

import html
import logging
from datetime import UTC, datetime, timedelta, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.models import Payment, Shop, User
from app.services import billing
from app.services.notify import TelegramNotifier, shared_bot
from app.services.telegram import TelegramClient, TelegramError

logger = logging.getLogger(__name__)

# Iran has no daylight saving time since 2022.
TEHRAN = timezone(timedelta(hours=3, minutes=30))
_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(value: int | float | str) -> str:
    """Persian digits with Persian thousands separators: 12500 -> '۱۲٬۵۰۰'."""
    if isinstance(value, int | float):
        value = f"{int(value):,}".replace(",", "٬")
    return str(value).translate(_FA_DIGITS)


def toman(rial: int) -> str:
    return f"{fa(rial // 10)} تومان"


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=False)


def jalali(moment: datetime, with_time: bool = True) -> str:
    """'۱۴۰۵/۰۷/۱۲ ۱۴:۳۰' in Tehran time."""
    local = (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(TEHRAN)
    y, m, d = _to_jalali(local.year, local.month, local.day)
    text = f"{y}/{m:02d}/{d:02d}"
    if with_time:
        text += f" {local.hour:02d}:{local.minute:02d}"
    return fa(text)


def _to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """Gregorian -> Jalali (the standard arithmetic conversion)."""
    g_days = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666
        + 365 * gy
        + (gy2 + 3) // 4
        - (gy2 + 99) // 100
        + (gy2 + 399) // 400
        + gd
        + g_days[gm - 1]
    )
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


async def announce(db: AsyncSession, http: httpx.AsyncClient, text: str) -> None:
    """Send `text` (Telegram HTML) to the team."""
    settings = get_settings()
    targets: list[int | str] = (
        [settings.ops_telegram_chat_id]
        if settings.ops_telegram_chat_id
        else sorted(settings.ops_admin_ids)
    )
    if not targets:
        return
    try:
        bot = await shared_bot(db, "telegram")
        if bot is None:
            return
        token = decrypt_secret(bot.token_encrypted)
        client = TelegramClient(http)
        for chat in targets:
            try:
                await client.send_message(token, chat, text[:4000], html=True, disable_preview=True)
            except TelegramError as exc:
                logger.info("team announcement to %s failed: %s", chat, exc)
    except Exception:
        logger.exception("team announcement failed")


async def new_signup(db: AsyncSession, http: httpx.AsyncClient, user: User, shop: Shop) -> None:
    await announce(
        db,
        http,
        f"🆕 <b>ثبت‌نام تازه</b>\n🏪 {esc(shop.name)}\n👤 <code>{esc(user.email)}</code>"
        + (f" · {esc(user.full_name)}" if user.full_name else ""),
    )


async def topup_paid(db: AsyncSession, http: httpx.AsyncClient, payment: Payment) -> None:
    """Tell the owner their wallet was charged, and the team that money came in."""
    shop = await db.get(Shop, payment.shop_id)
    if shop is None:
        return
    try:
        await TelegramNotifier(db, TelegramClient(http)).message(
            shop,
            f"✅ کیف پول «جواب» {billing.toman(payment.amount_rial)} شارژ شد.\n"
            f"موجودی فعلی: {billing.toman(shop.balance_rial)}",
        )
    except Exception:
        logger.exception("could not tell shop %s about its top-up", shop.id)
    await announce(
        db,
        http,
        f"💰 <b>شارژ کیف پول</b>\n🏪 {esc(shop.name)}\n💵 {toman(payment.amount_rial)}"
        f" · {esc(payment.gateway)}",
    )
