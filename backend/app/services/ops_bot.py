"""The team's admin panel, inside the shared Telegram bot (@JavabAppBot).

Members of OPS_ADMIN_TELEGRAM_IDS send /ops and get one message that works like an app: every
button edits that same message in place (home, shops, a shop's card, payments, trends, system
status). Actions that change money or accounts always show a confirmation first, and every
wallet change is recorded in the shop's ledger with who made it.

    /ops ─► 🏠 home ─┬─ 🏪 shops (newest / top usage / low balance) ─► shop card
                     │      └─ ➕ credit · ➖ debit · 📜 ledger · ✉️ message · ⛔️ suspend
                     ├─ 🔍 search (email, name, code, mobile)
                     ├─ 💳 payments   ├─ 📈 last 7 days   ├─ 📣 message all owners
                     └─ ⚙️ system status

Typed input (an amount, a search, a message) is remembered in the admin's bot session under
"ops", so it never mixes with the owner flows of the same chat.
"""

import asyncio
import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import Select, and_, func, or_, select

from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.core.timeutil import utcnow
from app.models import (
    Conversation,
    Message,
    MessageSender,
    Payment,
    PaymentStatus,
    Product,
    Shop,
    TelegramAdmin,
    TelegramBot,
    TelegramSession,
    User,
    WalletEntry,
    WalletEntryKind,
)
from app.services import billing
from app.services.notify import TelegramNotifier, inline_keyboard, shared_bot
from app.services.ops import TEHRAN, esc, fa, jalali, toman
from app.services.telegram import TelegramError

if TYPE_CHECKING:
    from app.services.telegram_bot import _Bot

logger = logging.getLogger(__name__)

PAGE = 8
LINE = "━━━━━━━━━━━━━━"
MAX_AMOUNT_TOMAN = 100_000_000
_FA_TO_EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_AMOUNT = re.compile(r"^\s*([\d,٬.\s]+?)\s*(?:تومان|ت)?(?:\s+(.*))?$", re.S)

Screen = tuple[str, dict[str, Any]]


def is_ops(h: "_Bot", user_id: int) -> bool:
    """Only on the shared Telegram bot, and only for the team's accounts."""
    return (
        h.bot.is_shared and h.bot.platform == "telegram" and user_id in get_settings().ops_admin_ids
    )


def _kb(rows: list[list[tuple[str, str]]]) -> dict[str, Any]:
    return inline_keyboard(rows)


def _state(session: TelegramSession) -> dict[str, Any]:
    return dict((session.state or {}).get("ops") or {})


def _set_state(session: TelegramSession, ops: dict[str, Any] | None) -> None:
    state = {k: v for k, v in (session.state or {}).items() if k != "ops"}
    if ops:
        state["ops"] = ops
    session.state = state


def _day_start(days_ago: int = 0) -> datetime:
    """Midnight in Tehran, `days_ago` days back, as a UTC-aware datetime."""
    local = utcnow().astimezone(TEHRAN)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
    return midnight


# ---------------------------------------------------------------------------- entry points


async def open_panel(h: "_Bot", session: TelegramSession, chat_id: int) -> None:
    """/ops: a fresh panel message."""
    _set_state(session, None)
    await h.db.commit()
    text, keyboard = await _home(h)
    await _send(h, chat_id, text, keyboard)


async def on_text(h: "_Bot", session: TelegramSession, chat_id: int, text: str) -> bool:
    """Typed input the panel asked for. False if the panel wasn't waiting for anything."""
    ops = _state(session)
    waiting = ops.get("await")
    if not waiting:
        return False
    if text.startswith("/"):
        _set_state(session, None)
        await h.db.commit()
        return False
    await _drop_buttons(h, chat_id, ops.get("msg"))
    if waiting == "search":
        _set_state(session, None)
        await h.db.commit()
        screen = await _search(h, text)
    elif waiting in ("credit", "debit"):
        screen = await _amount_entered(h, session, ops, text)
    elif waiting in ("msg", "bc"):
        screen = await _message_entered(h, session, ops, text)
    else:
        _set_state(session, None)
        await h.db.commit()
        screen = await _home(h)
    message_id = await _send(h, chat_id, *screen)
    ops = _state(session)
    if ops:
        ops["msg"] = message_id
        _set_state(session, ops)
        await h.db.commit()
    return True


async def on_callback(h: "_Bot", query: dict[str, Any]) -> str:
    """A panel button. Returns the short notice shown on the button press."""
    user_id = int((query.get("from") or {}).get("id") or 0)
    if not is_ops(h, user_id):
        return "دسترسی ندارید."
    message = query.get("message") or {}
    chat_id = int((message.get("chat") or {}).get("id") or user_id)
    message_id = int(message.get("message_id") or 0)
    parts = str(query.get("data") or "").split(":")[1:]
    action, args = (parts[0] if parts else "home"), parts[1:]
    session = await _session(h, user_id)
    notice = ""
    try:
        screen, notice = await _route(h, session, action, args, user_id, message_id)
    except Exception:
        logger.exception("ops panel action %s failed", action)
        screen, notice = await _home(h), "خطا؛ دوباره امتحان کنید."
    await _edit(h, chat_id, message_id, *screen)
    return notice


async def _route(
    h: "_Bot", session: TelegramSession, action: str, args: list[str], user_id: int, msg: int
) -> tuple[Screen, str]:
    if action in ("home", "refresh"):
        _set_state(session, None)
        await h.db.commit()
        return await _home(h), ("به‌روز شد" if action == "refresh" else "")
    if action == "shops":
        sort = args[0] if args else "new"
        page = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
        return await _shops(h, sort, page), ""
    if action == "shop":
        return await _shop_screen(h, args[0]), ""
    if action == "tx":
        return await _ledger(h, args[0]), ""
    if action in ("credit", "debit", "msg"):
        shop = await _shop(h, args[0])
        if shop is None:
            return await _home(h), "فروشگاه پیدا نشد."
        _set_state(session, {"await": action, "shop": str(shop.id), "msg": msg})
        await h.db.commit()
        return _prompt(action, shop), ""
    if action == "search":
        _set_state(session, {"await": "search", "msg": msg})
        await h.db.commit()
        return _prompt("search"), ""
    if action == "bc":
        _set_state(session, {"await": "bc", "msg": msg})
        await h.db.commit()
        return _prompt("bc"), ""
    if action == "susp":
        return await _suspend_confirm(h, session, args[0], msg), ""
    if action == "unsusp":
        return await _set_suspended(h, args[0], False), "حساب فعال شد"
    if action == "ok":
        return await _confirm(h, session, user_id)
    if action == "cancel":
        ops = _state(session)
        _set_state(session, None)
        await h.db.commit()
        if ops.get("shop"):
            return await _shop_screen(h, ops["shop"]), "لغو شد"
        return await _home(h), "لغو شد"
    if action == "pay":
        return await _payments(h), ""
    if action == "trend":
        return await _trend(h), ""
    if action == "sys":
        return await _system(h), ""
    return await _home(h), ""


# ---------------------------------------------------------------------------- screens


async def _count(h: "_Bot", query: Select) -> int:
    return int(await h.db.scalar(select(func.count()).select_from(query.subquery())) or 0)


async def _sum(h: "_Bot", column: Any, *where: Any) -> int:
    return int(await h.db.scalar(select(func.coalesce(func.sum(column), 0)).where(*where)) or 0)


async def _home(h: "_Bot") -> Screen:
    today, week, month = _day_start(0), _day_start(6), _day_start(29)
    shops = await _count(h, select(Shop.id))
    shops_today = await _count(h, select(Shop.id).where(Shop.created_at >= today))
    shops_week = await _count(h, select(Shop.id).where(Shop.created_at >= week))
    linked = await _count(h, select(TelegramAdmin.shop_id).distinct())
    gifted = await _count(h, select(Shop.id).where(Shop.signup_gift_at.is_not(None)))
    bots_on = await _count(h, select(Shop.id).where(Shop.bot_enabled.is_(True)))
    active = await _count(
        h,
        select(Conversation.shop_id)
        .where(Conversation.last_customer_message_at >= week)
        .distinct(),
    )
    asked = await _count(
        h,
        select(Message.id).where(
            Message.created_at >= today, Message.sender == MessageSender.CUSTOMER
        ),
    )
    answered = await _count(
        h,
        select(Message.id).where(Message.created_at >= today, Message.sender == MessageSender.BOT),
    )
    handoffs = await _count(
        h,
        select(Conversation.id).where(
            Conversation.handoff_at.is_not(None), Conversation.handoff_resolved_at.is_(None)
        ),
    )
    topup_today = await _sum(
        h,
        WalletEntry.amount_rial,
        WalletEntry.kind == WalletEntryKind.TOPUP,
        WalletEntry.created_at >= today,
    )
    topup_month = await _sum(
        h,
        WalletEntry.amount_rial,
        WalletEntry.kind == WalletEntryKind.TOPUP,
        WalletEntry.created_at >= month,
    )
    usage_today = -await _sum(
        h,
        WalletEntry.amount_rial,
        WalletEntry.kind == WalletEntryKind.USAGE,
        WalletEntry.created_at >= today,
    )
    usage_month = -await _sum(
        h,
        WalletEntry.amount_rial,
        WalletEntry.kind.in_([WalletEntryKind.USAGE, WalletEntryKind.PLAN_FEE]),
        WalletEntry.created_at >= month,
    )
    balances = await _sum(h, Shop.balance_rial)
    pending = await _count(h, select(Payment.id).where(Payment.status == PaymentStatus.PENDING))

    text = "\n".join(
        [
            "🛠 <b>پنل مدیریت «جواب»</b>",
            LINE,
            f"🏪 فروشگاه‌ها: <b>{fa(shops)}</b>   امروز +{fa(shops_today)} · هفته +{fa(shops_week)}",
            f"🔗 پیام‌رسان وصل: {fa(linked)}   🎁 هدیه گرفته: {fa(gifted)}",
            f"🤖 ربات روشن: {fa(bots_on)}   🔥 فعال در ۷ روز: {fa(active)}",
            "",
            f"💬 امروز: {fa(asked)} پیام مشتری · {fa(answered)} جواب ربات",
            f"🙋 منتظر صاحب فروشگاه: <b>{fa(handoffs)}</b>",
            "",
            f"💰 شارژ امروز: <b>{toman(topup_today)}</b>",
            f"💰 شارژ ۳۰ روز: {toman(topup_month)}",
            f"⚡️ مصرف امروز: {toman(usage_today)}",
            f"⚡️ مصرف و پلن ۳۰ روز: {toman(usage_month)}",
            f"👛 مجموع موجودی کیف پول‌ها: {toman(balances)}",
            f"⏳ پرداخت در انتظار: {fa(pending)}",
            LINE,
            f"🕒 {jalali(utcnow())}",
        ]
    )
    keyboard = _kb(
        [
            [("🏪 فروشگاه‌ها", "ops:shops:new:0"), ("🔍 جستجو", "ops:search")],
            [("💳 پرداخت‌ها", "ops:pay"), ("📈 روند ۷ روز", "ops:trend")],
            [("📣 پیام به همه", "ops:bc"), ("⚙️ وضعیت سیستم", "ops:sys")],
            [("🔄 به‌روزرسانی", "ops:refresh")],
        ]
    )
    return text, keyboard


def _shop_button(shop: Shop, owner_active: bool) -> tuple[str, str]:
    icon = "⛔️" if not owner_active else ("🟢" if shop.bot_enabled else "⚪️")
    name = shop.name if len(shop.name) <= 22 else shop.name[:21] + "…"
    return f"{icon} {name} · {fa(shop.balance_rial // 10)}ت", f"ops:shop:{shop.id}"


async def _shops(h: "_Bot", sort: str, page: int) -> Screen:
    query = select(Shop, User.is_active).join(User, User.id == Shop.owner_id)
    titles = {"new": "تازه‌ترین", "top": "پرمصرف‌ترین (۳۰ روز)", "low": "کمترین موجودی"}
    sort = sort if sort in titles else "new"
    if sort == "top":
        usage = (
            select(WalletEntry.shop_id, func.sum(-WalletEntry.amount_rial).label("spent"))
            .where(
                WalletEntry.kind == WalletEntryKind.USAGE, WalletEntry.created_at >= _day_start(29)
            )
            .group_by(WalletEntry.shop_id)
            .subquery()
        )
        query = query.join(usage, usage.c.shop_id == Shop.id).order_by(usage.c.spent.desc())
    elif sort == "low":
        query = query.order_by(Shop.balance_rial.asc(), Shop.created_at.desc())
    else:
        query = query.order_by(Shop.created_at.desc())
    total = await _count(h, query)
    rows = (await h.db.execute(query.offset(page * PAGE).limit(PAGE))).all()
    pages = max(1, (total + PAGE - 1) // PAGE)
    text = "\n".join(
        [
            f"🏪 <b>فروشگاه‌ها</b> · {titles[sort]}",
            LINE,
            f"{fa(total)} فروشگاه · صفحه‌ی {fa(page + 1)} از {fa(pages)}",
            "🟢 ربات روشن  ⚪️ خاموش  ⛔️ معلق",
        ]
        + ([] if rows else ["", "چیزی پیدا نشد."])
    )
    buttons = [[_shop_button(shop, active)] for shop, active in rows]
    tabs = [
        (("• " if s == sort else "") + label, f"ops:shops:{s}:0")
        for s, label in (("new", "تازه"), ("top", "پرمصرف"), ("low", "کم‌موجودی"))
    ]
    nav = []
    if page > 0:
        nav.append(("◀️ قبلی", f"ops:shops:{sort}:{page - 1}"))
    if page + 1 < pages:
        nav.append(("بعدی ▶️", f"ops:shops:{sort}:{page + 1}"))
    keyboard = _kb([tabs, *buttons, *([nav] if nav else []), [("🏠 خانه", "ops:home")]])
    return text, keyboard


async def _shop(h: "_Bot", raw_id: str) -> Shop | None:
    try:
        return await h.db.get(Shop, uuid.UUID(raw_id))
    except ValueError:
        return None


async def _shop_screen(h: "_Bot", raw_id: str) -> Screen:
    shop = await _shop(h, raw_id)
    if shop is None:
        return await _home(h)
    owner = await h.db.get(User, shop.owner_id)
    assert owner is not None
    admins = (
        await h.db.scalars(select(TelegramAdmin).where(TelegramAdmin.shop_id == shop.id))
    ).all()
    own_bots = (
        await h.db.scalars(
            select(TelegramBot).where(TelegramBot.shop_id == shop.id, TelegramBot.is_active)
        )
    ).all()
    products = await _count(h, select(Product.id).where(Product.shop_id == shop.id))
    week = _day_start(6)
    chats = await _count(
        h,
        select(Conversation.id).where(
            Conversation.shop_id == shop.id, Conversation.last_customer_message_at >= week
        ),
    )
    waiting = await _count(
        h,
        select(Conversation.id).where(
            Conversation.shop_id == shop.id,
            Conversation.handoff_at.is_not(None),
            Conversation.handoff_resolved_at.is_(None),
        ),
    )
    last_seen = await h.db.scalar(
        select(func.max(Conversation.last_customer_message_at)).where(
            Conversation.shop_id == shop.id
        )
    )
    spent = -await _sum(
        h,
        WalletEntry.amount_rial,
        WalletEntry.shop_id == shop.id,
        WalletEntry.kind == WalletEntryKind.USAGE,
        WalletEntry.created_at >= _day_start(29),
    )
    paid = await _sum(
        h,
        WalletEntry.amount_rial,
        WalletEntry.shop_id == shop.id,
        WalletEntry.kind == WalletEntryKind.TOPUP,
    )

    def mark(ok: bool) -> str:
        return "✅" if ok else "—"

    platforms = {a.platform for a in admins}
    usernames = ", ".join(f"@{esc(a.username)}" for a in admins if a.username)
    phone = owner.phone.replace("+98", "0") if owner.phone else ""
    status = "⛔️ <b>معلق</b>" if not owner.is_active else "✅ فعال"
    lines = [
        f"🏪 <b>{esc(shop.name)}</b>  <code>{esc(shop.slug)}</code>",
        LINE,
        f"👤 <code>{esc(owner.email)}</code> {'✅' if owner.email_verified_at else '⚠️'}"
        + (f" · {esc(owner.full_name)}" if owner.full_name else ""),
        f"📱 {fa(phone) + ' ✅' if phone else 'شماره تأیید نشده'}",
        f"🔗 تلگرام {mark('telegram' in platforms)}  بله {mark('bale' in platforms)}"
        + (f"  {usernames}" if usernames else ""),
        f"🤖 ربات: {'روشن 🟢' if shop.bot_enabled else 'خاموش ⚪️'}"
        + (
            "  · ربات اختصاصی: " + ", ".join(f"@{esc(b.username)}" for b in own_bots)
            if own_bots
            else ""
        ),
        "",
        f"💰 موجودی: <b>{toman(shop.balance_rial)}</b>",
        f"📦 پلن: {billing.PLANS[shop.plan].label}"
        + (f" (تمدید {jalali(shop.plan_renews_at, False)})" if shop.plan_renews_at else ""),
        f"⚡️ مصرف ۳۰ روز: {toman(spent)}   💵 کل شارژها: {toman(paid)}",
        f"🎁 هدیه: {jalali(shop.signup_gift_at, False) if shop.signup_gift_at else 'نگرفته'}",
        "",
        f"🛍 محصولات: {fa(products)}   💬 گفتگوی ۷ روز: {fa(chats)}   🙋 منتظر: {fa(waiting)}",
        f"🗓 عضویت: {jalali(shop.created_at, False)}"
        + (f"   آخرین پیام مشتری: {jalali(last_seen)}" if last_seen else ""),
        f"وضعیت حساب: {status}",
    ]
    sid = str(shop.id)
    suspend = (
        ("▶️ رفع تعلیق", f"ops:unsusp:{sid}")
        if not owner.is_active
        else (
            "⛔️ تعلیق",
            f"ops:susp:{sid}",
        )
    )
    keyboard = _kb(
        [
            [("➕ شارژ دستی", f"ops:credit:{sid}"), ("➖ کسر", f"ops:debit:{sid}")],
            [("📜 تراکنش‌ها", f"ops:tx:{sid}"), ("✉️ پیام به صاحب", f"ops:msg:{sid}")],
            [suspend, ("🔄", f"ops:shop:{sid}")],
            [("🔙 فروشگاه‌ها", "ops:shops:new:0"), ("🏠 خانه", "ops:home")],
        ]
    )
    return "\n".join(lines), keyboard


async def _ledger(h: "_Bot", raw_id: str) -> Screen:
    shop = await _shop(h, raw_id)
    if shop is None:
        return await _home(h)
    entries = (
        await h.db.scalars(
            select(WalletEntry)
            .where(WalletEntry.shop_id == shop.id)
            .order_by(WalletEntry.created_at.desc())
            .limit(15)
        )
    ).all()
    icons = {
        WalletEntryKind.TOPUP: "💵",
        WalletEntryKind.USAGE: "⚡️",
        WalletEntryKind.PLAN_FEE: "📦",
        WalletEntryKind.BONUS: "🎁",
        WalletEntryKind.ADJUSTMENT: "🛠",
    }
    lines = [f"📜 <b>تراکنش‌های {esc(shop.name)}</b>", LINE]
    for e in entries:
        sign = "+" if e.amount_rial >= 0 else "−"
        lines.append(
            f"{icons.get(e.kind, '•')} {sign}{fa(abs(e.amount_rial) // 10)}ت  "
            f"<i>{esc(e.description[:40])}</i>\n      {jalali(e.created_at)} · "
            f"مانده {fa(e.balance_after_rial // 10)}ت"
        )
    if not entries:
        lines.append("هنوز تراکنشی نیست.")
    keyboard = _kb([[("🔙 فروشگاه", f"ops:shop:{shop.id}"), ("🏠 خانه", "ops:home")]])
    return "\n".join(lines), keyboard


async def _payments(h: "_Bot") -> Screen:
    rows = (
        await h.db.execute(
            select(Payment, Shop.name)
            .join(Shop, Shop.id == Payment.shop_id)
            .order_by(Payment.created_at.desc())
            .limit(15)
        )
    ).all()
    icons = {PaymentStatus.PAID: "✅", PaymentStatus.PENDING: "⏳", PaymentStatus.FAILED: "❌"}
    stale = utcnow() - timedelta(hours=1)
    lines = ["💳 <b>آخرین پرداخت‌ها</b>", LINE]
    for payment, name in rows:
        late = (
            " ⚠️ دیر"
            if payment.status == PaymentStatus.PENDING and payment.created_at < stale
            else ""
        )
        lines.append(
            f"{icons.get(payment.status, '•')} {toman(payment.amount_rial)} · {esc(name[:24])}"
            f"\n      {jalali(payment.created_at)} · {esc(payment.gateway)}{late}"
        )
    if not rows:
        lines.append("هنوز پرداختی نیست.")
    lines += [LINE, "⏳ در انتظار  ✅ موفق  ❌ ناموفق یا منقضی"]
    return "\n".join(lines), _kb([[("🔄", "ops:pay"), ("🏠 خانه", "ops:home")]])


async def _trend(h: "_Bot") -> Screen:
    lines = ["📈 <b>روند ۷ روز گذشته</b>", LINE, "روز · ثبت‌نام · شارژ · مصرف"]
    for days_ago in range(6, -1, -1):
        start, end = _day_start(days_ago), _day_start(days_ago - 1)
        signups = await _count(
            h, select(Shop.id).where(Shop.created_at >= start, Shop.created_at < end)
        )
        topups = await _sum(
            h,
            WalletEntry.amount_rial,
            WalletEntry.kind == WalletEntryKind.TOPUP,
            WalletEntry.created_at >= start,
            WalletEntry.created_at < end,
        )
        usage = -await _sum(
            h,
            WalletEntry.amount_rial,
            WalletEntry.kind == WalletEntryKind.USAGE,
            WalletEntry.created_at >= start,
            WalletEntry.created_at < end,
        )
        day = jalali(start, False)[5:]  # MM/DD
        lines.append(
            f"<code>{day}</code>  👤 {fa(signups)}  💵 {fa(topups // 10)}ت  ⚡️ {fa(usage // 10)}ت"
        )
    return "\n".join(lines), _kb([[("🔄", "ops:trend"), ("🏠 خانه", "ops:home")]])


async def _system(h: "_Bot") -> Screen:
    settings = get_settings()

    def state(ok: bool, detail: str = "") -> str:
        return ("✅" if ok else "❌") + (f" {detail}" if detail else "")

    def handle(bot: TelegramBot | None) -> str:
        return f"@{esc(bot.username)}" if bot else ""

    telegram_bot = await shared_bot(h.db, "telegram")
    bale_bot = await shared_bot(h.db, "bale")
    gateway = settings.payment_gateway.strip().lower() or "aban"
    if gateway == "zarinpal":
        gateway_ok = bool(settings.zarinpal_merchant_id)
        gateway_detail = "زرین‌پال" + (" (سندباکس)" if settings.zarinpal_sandbox else "")
    else:
        gateway_ok = bool(settings.aban_api_token and settings.aban_webhook_secret)
        gateway_detail = "آبان گیت‌وی" + (
            " (تست)" if settings.aban_api_token.startswith("ag_test_") else ""
        )
    stale = await _count(
        h,
        select(Payment.id).where(
            Payment.status == PaymentStatus.PENDING,
            Payment.created_at < utcnow() - timedelta(hours=1),
        ),
    )
    gift = settings.signup_credit_rial if settings.billing_enabled else 0
    lines = [
        "⚙️ <b>وضعیت سیستم</b>",
        LINE,
        f"🧠 هوش مصنوعی: {state(settings.llm_configured, esc(settings.llm_model))}",
        f"✈️ ربات تلگرام: {state(telegram_bot is not None, handle(telegram_bot))}",
        f"🟢 ربات بله: {state(bale_bot is not None, handle(bale_bot))}",
        f"📷 اینستاگرام: {'روشن' if settings.instagram_enabled else 'خاموش (منتظر متا)'}",
        "",
        f"💳 درگاه: {state(gateway_ok, gateway_detail)}",
        f"👛 کیف پول: {'روشن' if settings.billing_enabled else 'خاموش (رایگان)'}"
        f" · هر جواب حدود {toman(billing.usage_cost(4000, 150))}",
        f"🎁 هدیه: {toman(gift) if gift else 'ندارد'}"
        + (" · با تأیید شماره" if gift and settings.signup_gift_requires_phone else ""),
        "",
        f"📱 پیامک: {state(bool(settings.sms_provider), esc(settings.sms_provider))}",
        f"✉️ ایمیل: {state(bool(settings.smtp_host), esc(settings.smtp_host))}",
        f"🐞 Sentry: {state(bool(settings.sentry_dsn))}",
        f"🚨 گروه هشدار خطا: {state(bool(settings.ops_telegram_chat_id))}",
        "",
        f"⏳ پرداخت معلق بیش از ۱ ساعت: {fa(stale)}" + (" ⚠️" if stale else ""),
        f"🌐 محیط: {esc(settings.environment)}",
    ]
    return "\n".join(lines), _kb([[("🔄", "ops:sys"), ("🏠 خانه", "ops:home")]])


async def _search(h: "_Bot", text: str) -> Screen:
    term = text.strip().translate(_FA_TO_EN)[:100]
    digits = re.sub(r"\D", "", term)
    conditions = [
        Shop.name.ilike(f"%{term}%"),
        User.email.ilike(f"%{term}%"),
        Shop.slug == term.lower(),
        User.full_name.ilike(f"%{term}%"),
    ]
    if len(digits) >= 6:
        conditions.append(User.phone.like(f"%{digits.lstrip('0')[-10:]}%"))
    rows = (
        await h.db.execute(
            select(Shop, User.is_active)
            .join(User, User.id == Shop.owner_id)
            .where(or_(*conditions))
            .order_by(Shop.created_at.desc())
            .limit(PAGE)
        )
    ).all()
    lines = [f"🔍 <b>نتیجه‌ی جستجو</b>: {esc(text[:60])}", LINE]
    lines.append(f"{fa(len(rows))} فروشگاه" if rows else "چیزی پیدا نشد.")
    buttons = [[_shop_button(shop, active)] for shop, active in rows]
    keyboard = _kb([*buttons, [("🔍 جستجوی دیگر", "ops:search"), ("🏠 خانه", "ops:home")]])
    return "\n".join(lines), keyboard


# ---------------------------------------------------------------------------- input and actions


def _prompt(action: str, shop: Shop | None = None) -> Screen:
    name = f"«{esc(shop.name)}»" if shop else ""
    texts = {
        "credit": f"➕ <b>شارژ دستی کیف پول {name}</b>\n\nمبلغ را به <b>تومان</b> بفرستید؛ "
        "بعد از عدد می‌توانید توضیح هم بنویسید:\n<code>200000 کارت به کارت ۱۲ مهر</code>",
        "debit": f"➖ <b>کسر از کیف پول {name}</b>\n\nمبلغ را به <b>تومان</b> بفرستید؛ "
        "بعد از عدد دلیلش را بنویسید:\n<code>50000 برگشت هدیه‌ی تکراری</code>",
        "msg": f"✉️ <b>پیام به صاحب {name}</b>\n\nمتن پیام را بفرستید؛ قبل از ارسال "
        "پیش‌نمایش را می‌بینید.",
        "search": "🔍 <b>جستجوی فروشگاه</b>\n\nایمیل، اسم فروشگاه، کد فروشگاه، اسم صاحب یا "
        "شماره موبایل را بفرستید.",
        "bc": "📣 <b>پیام به همه‌ی صاحبان فروشگاه</b>\n\nمتن پیام را بفرستید. به همه‌ی کسانی "
        "که تلگرام یا بله‌شان را وصل کرده‌اند می‌رسد؛ قبل از ارسال پیش‌نمایش را می‌بینید.",
    }
    back = ("❌ لغو", "ops:cancel")
    return texts[action], _kb([[back]])


def parse_amount(text: str) -> tuple[int, str] | None:
    """'۲۰۰٬۰۰۰ کارت به کارت' -> (200000, 'کارت به کارت')."""
    match = _AMOUNT.match(text.translate(_FA_TO_EN))
    if not match:
        return None
    digits = re.sub(r"[,٬.\s]", "", match.group(1))
    if not digits.isdigit():
        return None
    amount = int(digits)
    if not 0 < amount <= MAX_AMOUNT_TOMAN:
        return None
    return amount, (match.group(2) or "").strip()[:200]


async def _amount_entered(
    h: "_Bot", session: TelegramSession, ops: dict[str, Any], text: str
) -> Screen:
    shop = await _shop(h, str(ops.get("shop")))
    if shop is None:
        _set_state(session, None)
        await h.db.commit()
        return await _home(h)
    parsed = parse_amount(text)
    if parsed is None:
        return (
            "⚠️ مبلغ را نفهمیدم. فقط عدد به تومان، مثل <code>200000</code>، و بعدش توضیح.",
            _kb([[("❌ لغو", "ops:cancel")]]),
        )
    amount, note = parsed
    debit = ops.get("await") == "debit"
    if debit and amount * 10 > shop.balance_rial:
        return (
            f"⚠️ موجودی «{esc(shop.name)}» فقط {toman(shop.balance_rial)} است؛ مبلغ کمتری بفرستید.",
            _kb([[("❌ لغو", "ops:cancel")]]),
        )
    ops["await"] = None
    ops["pending"] = {"kind": "debit" if debit else "credit", "amount": amount, "note": note}
    _set_state(session, ops)
    await h.db.commit()
    after = shop.balance_rial + (-1 if debit else 1) * amount * 10
    verb = "از کیف پول" if debit else "به کیف پول"
    action = "کسر شود" if debit else "اضافه شود"
    lines = [
        f"{'➖' if debit else '➕'} <b>{fa(amount)} تومان</b> {verb} «{esc(shop.name)}» {action}؟",
        f"موجودی: {toman(shop.balance_rial)} ← <b>{toman(after)}</b>",
    ]
    if note:
        lines.append(f"توضیح: <i>{esc(note)}</i>")
    lines.append("صاحب فروشگاه در تلگرام یا بله خبردار می‌شود.")
    return "\n".join(lines), _kb([[("✅ تأیید", "ops:ok"), ("❌ لغو", "ops:cancel")]])


async def _recipients(h: "_Bot") -> list[TelegramAdmin]:
    return list(
        (
            await h.db.scalars(
                select(TelegramAdmin)
                .join(Shop, Shop.id == TelegramAdmin.shop_id)
                .join(User, User.id == Shop.owner_id)
                .where(TelegramAdmin.notify.is_(True), User.is_active.is_(True))
            )
        ).all()
    )


async def _message_entered(
    h: "_Bot", session: TelegramSession, ops: dict[str, Any], text: str
) -> Screen:
    body = text.strip()[:3500]
    broadcast = ops.get("await") == "bc"
    ops["await"] = None
    ops["pending"] = {"kind": "bc" if broadcast else "msg", "text": body}
    _set_state(session, ops)
    await h.db.commit()
    if broadcast:
        count = len(await _recipients(h))
        head = f"📣 <b>پیش‌نمایش پیام همگانی</b> (به {fa(count)} اکانت)"
    else:
        shop = await _shop(h, str(ops["shop"]))
        head = f"✉️ <b>پیش‌نمایش پیام به «{esc(shop.name if shop else '')}»</b>"
    preview = f"{head}\n{LINE}\n📩 پیام از تیم «جواب»:\n\n{esc(body)}"
    return preview, _kb([[("✅ ارسال", "ops:ok"), ("❌ لغو", "ops:cancel")]])


async def _suspend_confirm(h: "_Bot", session: TelegramSession, raw_id: str, msg: int) -> Screen:
    shop = await _shop(h, raw_id)
    if shop is None:
        return await _home(h)
    _set_state(session, {"shop": str(shop.id), "msg": msg, "pending": {"kind": "suspend"}})
    await h.db.commit()
    text = (
        f"⛔️ <b>تعلیق «{esc(shop.name)}»؟</b>\n\n"
        "• صاحب فروشگاه دیگر نمی‌تواند وارد پنل شود و از ربات مدیریتش کند.\n"
        "• ربات فروشگاه خاموش می‌شود و به مشتری‌ها جواب نمی‌دهد.\n"
        "• داده‌ها و موجودی دست نمی‌خورند و با «رفع تعلیق» برمی‌گردد."
    )
    return text, _kb([[("⛔️ بله، تعلیق کن", "ops:ok"), ("❌ لغو", "ops:cancel")]])


async def _set_suspended(h: "_Bot", raw_id: str, suspended: bool) -> Screen:
    shop = await _shop(h, raw_id)
    if shop is None:
        return await _home(h)
    owner = await h.db.get(User, shop.owner_id)
    if owner is not None:
        owner.is_active = not suspended
        if suspended:
            shop.bot_enabled = False
        await h.db.commit()
        await _tell_owner(
            h,
            shop,
            "⛔️ حساب «جواب» شما موقتا معلق شد و ربات فعلا جواب نمی‌دهد. "
            "برای پیگیری به پشتیبانی پیام بدهید."
            if suspended
            else "✅ حساب «جواب» شما دوباره فعال شد. ربات را از پنل یا همین‌جا روشن کنید.",
        )
    return await _shop_screen(h, raw_id)


async def _confirm(h: "_Bot", session: TelegramSession, user_id: int) -> tuple[Screen, str]:
    ops = _state(session)
    pending = ops.get("pending") or {}
    _set_state(session, None)
    await h.db.commit()
    kind = pending.get("kind")
    if kind == "bc":
        sent, failed = await _broadcast(h, str(pending.get("text") or ""))
        text = f"📣 پیام همگانی فرستاده شد.\n✅ {fa(sent)} اکانت" + (
            f"   ❌ {fa(failed)} ناموفق" if failed else ""
        )
        return (text, _kb([[("🏠 خانه", "ops:home")]])), "ارسال شد"
    shop = await _shop(h, str(ops.get("shop") or ""))
    if shop is None:
        return await _home(h), "این کار منقضی شده؛ دوباره شروع کنید."
    if kind in ("credit", "debit"):
        amount = int(pending.get("amount") or 0) * 10
        note = str(pending.get("note") or "")
        if kind == "debit":
            await h.db.refresh(shop)
            if amount > shop.balance_rial:
                return await _shop_screen(h, str(shop.id)), "موجودی کافی نیست."
        signed = amount if kind == "credit" else -amount
        label = "شارژ دستی" if kind == "credit" else "کسر دستی"
        await billing.apply(
            h.db,
            shop,
            signed,
            WalletEntryKind.ADJUSTMENT,
            f"{label}{' — ' + note if note else ''}",
            {"by_telegram_id": user_id, "note": note},
        )
        logger.info("ops %s: %s %s rial for shop %s (%s)", user_id, kind, amount, shop.id, note)
        verb = (
            "به کیف پول «جواب» شما اضافه شد" if kind == "credit" else "از کیف پول «جواب» شما کسر شد"
        )
        await _tell_owner(
            h,
            shop,
            f"{'💰' if kind == 'credit' else '🧾'} {billing.toman(amount)} {verb}."
            + (f"\nتوضیح: {note}" if note else "")
            + f"\nموجودی فعلی: {billing.toman(shop.balance_rial)}",
        )
        return await _shop_screen(h, str(shop.id)), "ثبت شد ✅"
    if kind == "msg":
        await _tell_owner(h, shop, f"📩 پیام از تیم «جواب»:\n\n{pending.get('text') or ''}")
        return await _shop_screen(h, str(shop.id)), "فرستاده شد ✅"
    if kind == "suspend":
        return await _set_suspended(h, str(shop.id), True), "معلق شد"
    return await _shop_screen(h, str(shop.id)), ""


async def _tell_owner(h: "_Bot", shop: Shop, text: str) -> None:
    try:
        await TelegramNotifier(h.db, h.ctx.client).message(shop, text)
    except Exception:
        logger.exception("could not message the owner of shop %s", shop.id)


async def _broadcast(h: "_Bot", text: str) -> tuple[int, int]:
    """Send to every linked owner account, gently (Telegram allows ~30 messages a second)."""
    sent = failed = 0
    tokens: dict[str, str | None] = {}
    for admin in await _recipients(h):
        if admin.platform not in tokens:
            bot = await shared_bot(h.db, admin.platform)
            tokens[admin.platform] = decrypt_secret(bot.token_encrypted) if bot else None
        token = tokens[admin.platform]
        if token is None:
            failed += 1
            continue
        try:
            await h.ctx.client.for_platform(admin.platform).send_message(
                token, admin.telegram_user_id, f"📩 پیام از تیم «جواب»:\n\n{text}"
            )
            sent += 1
        except TelegramError as exc:
            failed += 1
            if exc.blocked:
                admin.notify = False
        await asyncio.sleep(0.05)
    await h.db.commit()
    return sent, failed


# ---------------------------------------------------------------------------- telegram plumbing


async def _session(h: "_Bot", user_id: int) -> TelegramSession:
    session = await h.db.scalar(
        select(TelegramSession).where(
            and_(TelegramSession.bot_id == h.bot.id, TelegramSession.telegram_user_id == user_id)
        )
    )
    if session is None:
        session = TelegramSession(bot_id=h.bot.id, telegram_user_id=user_id, state={})
        h.db.add(session)
        await h.db.commit()
    return session


async def _send(h: "_Bot", chat_id: int, text: str, keyboard: dict[str, Any]) -> int | None:
    try:
        return await h.client.send_message(
            h.token, chat_id, text, reply_markup=keyboard, disable_preview=True, html=True
        )
    except TelegramError as exc:
        logger.warning("ops panel send failed: %s", exc)
        return None


async def _edit(h: "_Bot", chat_id: int, message_id: int, text: str, keyboard: dict) -> None:
    if not message_id:
        await _send(h, chat_id, text, keyboard)
        return
    try:
        await h.client.edit_message_text(
            h.token, chat_id, message_id, text, reply_markup=keyboard, html=True
        )
    except TelegramError as exc:
        if "not modified" in str(exc).lower():
            return
        # Too old to edit, or deleted: show it as a new message.
        await _send(h, chat_id, text, keyboard)


async def _drop_buttons(h: "_Bot", chat_id: int, message_id: Any) -> None:
    if not message_id:
        return
    try:
        await h.client.edit_reply_markup(h.token, chat_id, int(message_id), None)
    except TelegramError:
        pass
