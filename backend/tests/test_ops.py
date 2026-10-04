"""The team's admin panel inside the shared Telegram bot (/ops)."""

from datetime import UTC, datetime
from itertools import count

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Shop, TelegramBot, User, WalletEntry, WalletEntryKind
from app.services import ops_bot
from app.services.ops import fa, jalali
from tests.conftest import FakeWeb, RecordingQueue
from tests.test_telegram import OWNER, _link_owner, _private, _update, setup  # noqa: F401

TEAM = 9001
_ids = count(50_000)


@pytest.fixture
def team(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "ops_admin_telegram_ids", f"{TEAM}, 9002")


def _press(data: str, user_id: int = TEAM, message_id: int = 77) -> dict:
    return {
        "update_id": next(_ids),
        "callback_query": {
            "id": f"cb{next(_ids)}",
            "from": {"id": user_id},
            "data": data,
            "message": {"message_id": message_id, "chat": {"id": user_id}},
        },
    }


def _screen(fake_web: FakeWeb) -> dict:
    """The last thing the panel showed (an edit in place or a new message)."""
    for _, method, payload in reversed(fake_web.telegram.calls):
        if method in ("editMessageText", "sendMessage"):
            return payload
    raise AssertionError("nothing shown")


def _buttons(payload: dict) -> dict[str, str]:
    rows = (payload.get("reply_markup") or {}).get("inline_keyboard") or []
    return {b["text"]: b["callback_data"] for row in rows for b in row}


async def test_only_the_team_gets_the_panel(
    db: AsyncSession,
    setup: tuple[Shop, TelegramBot],  # noqa: F811
    fake_web: FakeWeb,
    queue: RecordingQueue,
    team: None,
) -> None:
    shop, bot = setup
    await _update(db, bot, fake_web, queue, _private(7777, "/ops"))
    assert "پنل مدیریت" not in fake_web.telegram.sent()[-1]["text"]

    await _update(db, bot, fake_web, queue, _press("ops:home", user_id=7777))
    assert fake_web.telegram.sent("answerCallbackQuery")[-1]["text"] == "دسترسی ندارید."

    await _update(db, bot, fake_web, queue, _private(TEAM, "/ops"))
    home = fake_web.telegram.sent()[-1]
    assert "پنل مدیریت" in home["text"] and home["parse_mode"] == "HTML"
    assert "🏪 فروشگاه‌ها" in _buttons(home)
    assert f"<b>{fa(1)}</b>" in home["text"]  # one shop


async def test_shops_card_and_manual_credit(
    db: AsyncSession,
    setup: tuple[Shop, TelegramBot],  # noqa: F811
    fake_web: FakeWeb,
    queue: RecordingQueue,
    team: None,
    billing_on: None,
) -> None:
    shop, bot = setup
    await _link_owner(db, shop, bot, fake_web, queue)
    await _update(db, bot, fake_web, queue, _press("ops:shops:new:0"))
    listing = _screen(fake_web)
    card_button = next(v for k, v in _buttons(listing).items() if "مزون مهسا" in k)
    assert card_button == f"ops:shop:{shop.id}"

    await _update(db, bot, fake_web, queue, _press(card_button))
    card = _screen(fake_web)
    assert "مزون مهسا" in card["text"] and "owner@shop.ir" in card["text"]
    assert _buttons(card)["➕ شارژ دستی"] == f"ops:credit:{shop.id}"

    await _update(db, bot, fake_web, queue, _press(f"ops:credit:{shop.id}"))
    assert "تومان" in _screen(fake_web)["text"]
    await _update(db, bot, fake_web, queue, _private(TEAM, "عدد نیست"))
    assert "نفهمیدم" in _screen(fake_web)["text"]
    await _update(db, bot, fake_web, queue, _private(TEAM, "۲۰۰٬۰۰۰ کارت به کارت"))
    preview = _screen(fake_web)
    assert "۲۰۰٬۰۰۰" in preview["text"] and "کارت به کارت" in preview["text"]
    await db.refresh(shop)
    assert shop.balance_rial == 0  # nothing happens before the OK

    await _update(db, bot, fake_web, queue, _press("ops:ok"))
    await db.refresh(shop)
    assert shop.balance_rial == 2_000_000
    entry = await db.scalar(select(WalletEntry).where(WalletEntry.shop_id == shop.id))
    assert entry is not None and entry.kind == WalletEntryKind.ADJUSTMENT
    assert entry.details["by_telegram_id"] == TEAM
    # The owner heard about it in their own chat.
    to_owner = [m for m in fake_web.telegram.sent() if m["chat_id"] == OWNER]
    assert "اضافه شد" in to_owner[-1]["text"]

    # Taking out more than the balance is refused.
    await _update(db, bot, fake_web, queue, _press(f"ops:debit:{shop.id}"))
    await _update(db, bot, fake_web, queue, _private(TEAM, "500000"))
    assert "فقط" in _screen(fake_web)["text"]
    await _update(db, bot, fake_web, queue, _press("ops:cancel"))
    await db.refresh(shop)
    assert shop.balance_rial == 2_000_000


async def test_suspending_a_shop(
    db: AsyncSession,
    setup: tuple[Shop, TelegramBot],  # noqa: F811
    fake_web: FakeWeb,
    queue: RecordingQueue,
    team: None,
) -> None:
    shop, bot = setup
    await _link_owner(db, shop, bot, fake_web, queue)
    await _update(db, bot, fake_web, queue, _press(f"ops:susp:{shop.id}"))
    assert "تعلیق" in _screen(fake_web)["text"]
    await _update(db, bot, fake_web, queue, _press("ops:ok"))
    owner = await db.scalar(select(User).where(User.email == "owner@shop.ir"))
    await db.refresh(shop)
    assert owner is not None and not owner.is_active and not shop.bot_enabled
    assert "معلق" in _screen(fake_web)["text"]

    # The suspended owner can't manage the shop from the bot any more.
    await _update(db, bot, fake_web, queue, _private(OWNER, "/admin"))
    assert "مدیریت" not in fake_web.telegram.sent()[-1]["text"]

    await _update(db, bot, fake_web, queue, _press(f"ops:unsusp:{shop.id}"))
    await db.refresh(owner)
    assert owner.is_active


async def test_search_message_and_overview_screens(
    db: AsyncSession,
    setup: tuple[Shop, TelegramBot],  # noqa: F811
    fake_web: FakeWeb,
    queue: RecordingQueue,
    team: None,
) -> None:
    shop, bot = setup
    await _link_owner(db, shop, bot, fake_web, queue)
    await _update(db, bot, fake_web, queue, _press("ops:search"))
    await _update(db, bot, fake_web, queue, _private(TEAM, "owner@shop"))
    found = _screen(fake_web)
    assert any(v == f"ops:shop:{shop.id}" for v in _buttons(found).values())

    await _update(db, bot, fake_web, queue, _press(f"ops:msg:{shop.id}"))
    await _update(db, bot, fake_web, queue, _private(TEAM, "سلام، سرور امشب ۱۰ دقیقه آپدیت می‌شود"))
    assert "پیش‌نمایش" in _screen(fake_web)["text"]
    await _update(db, bot, fake_web, queue, _press("ops:ok"))
    to_owner = [m for m in fake_web.telegram.sent() if m["chat_id"] == OWNER]
    assert "سرور امشب" in to_owner[-1]["text"]

    await _update(db, bot, fake_web, queue, _press("ops:bc"))
    await _update(db, bot, fake_web, queue, _private(TEAM, "قابلیت جدید اضافه شد"))
    assert fa(1) in _screen(fake_web)["text"]  # one linked account will get it
    await _update(db, bot, fake_web, queue, _press("ops:ok"))
    to_owner = [m for m in fake_web.telegram.sent() if m["chat_id"] == OWNER]
    assert "قابلیت جدید" in to_owner[-1]["text"]

    for screen, expected in (
        ("ops:pay", "پرداخت"),
        ("ops:trend", "روند"),
        ("ops:sys", "وضعیت سیستم"),
        (f"ops:tx:{shop.id}", "تراکنش"),
        ("ops:shops:top:0", "پرمصرف"),
        ("ops:shops:low:0", "کمترین"),
    ):
        await _update(db, bot, fake_web, queue, _press(screen))
        assert expected in _screen(fake_web)["text"], screen


def test_amounts_and_dates() -> None:
    assert ops_bot.parse_amount("۲۰۰٬۰۰۰ کارت به کارت") == (200_000, "کارت به کارت")
    assert ops_bot.parse_amount("50,000") == (50_000, "")
    assert ops_bot.parse_amount("50000 تومان برگشت") == (50_000, "برگشت")
    assert ops_bot.parse_amount("صد هزار") is None
    assert ops_bot.parse_amount("0") is None
    assert jalali(datetime(2026, 10, 4, 12, 0, tzinfo=UTC)) == "۱۴۰۵/۰۷/۱۲ ۱۵:۳۰"
    assert jalali(datetime(2026, 3, 21, 0, 0, tzinfo=UTC), False) == "۱۴۰۵/۰۱/۰۱"
