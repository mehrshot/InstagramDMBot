"""Bale (بله): the same bot as Telegram, through Bale's Telegram-compatible Bot API."""

import uuid
from datetime import datetime, timedelta
from itertools import count
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import encrypt_secret
from app.core.timeutil import utcnow
from app.models import Channel, Conversation, Plan, Shop, TelegramAdmin, TelegramBot, User
from app.services import telegram_bot
from app.services.llm import LLMClient
from app.services.messaging import reply_to_conversation
from app.services.notify import TelegramNotifier
from app.services.responder import Reply
from app.services.telegram import TelegramClient
from tests.conftest import FakeWeb, RecordingQueue

BALE_TOKEN = "555:bale-shared-token"
OWNER = 6001
CUSTOMER = 8001
_ids = count(5000)


class FixedResponder:
    def __init__(self, reply: Reply) -> None:
        self.reply = reply
        self.channels: list[Channel] = []

    async def generate(self, shop: Shop, history: list, *, channel: Channel, **_: Any) -> Reply:
        self.channels.append(channel)
        return self.reply


@pytest.fixture
async def setup(db: AsyncSession, fake_web: FakeWeb) -> tuple[Shop, TelegramBot]:
    fake_web.telegram.bots[BALE_TOKEN] = {"id": 555, "username": "JavabBaleBot", "first_name": "J"}
    user = User(email="owner@shop.ir", password_hash="x")
    user.shop = Shop(name="مزون مهسا", slug="mahsa", bot_enabled=True)
    bot = TelegramBot(
        platform="bale",
        shop_id=None,
        bot_user_id=555,
        username="JavabBaleBot",
        webhook_secret="bale-secret",
        token_encrypted=encrypt_secret(BALE_TOKEN),
    )
    db.add_all([user, bot])
    await db.commit()
    return user.shop, bot


def _ctx(db: AsyncSession, fake_web: FakeWeb, queue: RecordingQueue) -> telegram_bot.BotContext:
    client = TelegramClient(fake_web.client())
    return telegram_bot.BotContext(
        client=client,
        llm=LLMClient(fake_web.client()),
        http=fake_web.client(),
        queue=queue,
        notifier=TelegramNotifier(db, client),
        debounce_seconds=0,
    )


def _private(user_id: int, text: str) -> dict[str, Any]:
    return {
        "update_id": next(_ids),
        "message": {
            "message_id": next(_ids),
            "date": int(datetime.now().timestamp()),
            "chat": {"id": user_id, "type": "private"},
            "from": {"id": user_id, "first_name": "Reza"},
            "text": text,
        },
    }


async def _update(db, bot, fake_web, queue, update) -> None:  # type: ignore[no-untyped-def]
    await telegram_bot.process_update(db, bot, update, _ctx(db, fake_web, queue))


async def _run_replies(db, queue, fake_web, responder) -> None:  # type: ignore[no-untyped-def]
    client = TelegramClient(fake_web.client())
    jobs = [j for j in queue.jobs if j.function == "reply_conversation"]
    queue.jobs.clear()
    for job in jobs:
        conversation_id, trigger_at = job.args
        await reply_to_conversation(
            db,
            uuid.UUID(conversation_id),
            datetime.fromisoformat(trigger_at),
            None,
            responder,
            telegram=client,
            notifier=TelegramNotifier(db, client),
        )


async def test_webhook_secret_in_the_url(
    client: AsyncClient, setup: tuple[Shop, TelegramBot], queue: RecordingQueue
) -> None:
    _, bot = setup
    url = f"/webhooks/telegram/{bot.id}"
    update = {"update_id": 1, "message": {"text": "سلام"}}
    assert (await client.post(url, json=update)).status_code == 403
    assert (await client.post(f"{url}?secret=wrong", json=update)).status_code == 403
    assert (await client.post(f"{url}?secret=bale-secret", json=update)).status_code == 200
    assert [j.function for j in queue.jobs] == ["process_telegram_update"]


async def test_customer_on_bale(
    db: AsyncSession, setup: tuple[Shop, TelegramBot], fake_web: FakeWeb, queue: RecordingQueue
) -> None:
    shop, bot = setup
    # No start parameter: the customer sends the shop code instead.
    await _update(db, bot, fake_web, queue, _private(CUSTOMER, "/start"))
    await _update(db, bot, fake_web, queue, _private(CUSTOMER, "Mahsa"))
    assert "مزون مهسا" in fake_web.telegram.sent()[-1]["text"]
    assert set(fake_web.telegram.hosts) == {"bale.test"}

    await _update(db, bot, fake_web, queue, _private(CUSTOMER, "شومیز حریر دارید؟"))
    conversation = await db.scalar(select(Conversation))
    assert conversation is not None and conversation.channel == Channel.BALE

    responder = FixedResponder(Reply(text="بله، سفیدش موجوده"))
    await _run_replies(db, queue, fake_web, responder)
    assert responder.channels == [Channel.BALE]
    assert fake_web.telegram.sent()[-1] == {"chat_id": CUSTOMER, "text": "بله، سفیدش موجوده"}
    assert fake_web.telegram.hosts[-1] == "bale.test"


async def test_owner_on_bale_gets_alerts(
    db: AsyncSession, setup: tuple[Shop, TelegramBot], fake_web: FakeWeb, queue: RecordingQueue
) -> None:
    shop, bot = setup
    shop.telegram_link_code = "BALELINK1"
    shop.telegram_link_expires_at = utcnow() + timedelta(minutes=5)
    await db.commit()
    await _update(db, bot, fake_web, queue, _private(OWNER, "/start a_BALELINK1"))
    admin = await db.scalar(select(TelegramAdmin))
    assert admin is not None and admin.platform == "bale" and admin.shop_id == shop.id
    assert "حساب بله شما" in fake_web.telegram.sent()[-2]["text"]
    # The Telegram-only channel tip isn't offered on Bale.
    assert "کانال تلگرام" not in fake_web.telegram.sent()[-1]["text"]

    await _update(db, bot, fake_web, queue, _private(CUSTOMER, "/start s_mahsa"))
    await _update(db, bot, fake_web, queue, _private(CUSTOMER, "فاکتور رسمی می‌دید؟"))
    await _run_replies(
        db,
        queue,
        fake_web,
        FixedResponder(Reply(text="از همکارم می‌پرسم", unanswered=True, handoff_reason="فاکتور")),
    )
    alert = [m for m in fake_web.telegram.sent() if m["chat_id"] == OWNER][-1]
    assert "فاکتور رسمی می‌دید؟" in alert["text"]
    assert "reply_markup" in alert


async def test_custom_bale_bot(
    client: AsyncClient,
    auth_headers: dict,
    fake_web: FakeWeb,
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    fake_web.telegram.bots["777:shop-bale-bot"] = {
        "id": 777,
        "username": "MahsaBaleBot",
        "first_name": "M",
    }
    async with sessions() as db:
        shop = await db.scalar(select(Shop))
        assert shop is not None
        shop.plan = Plan.PRO
        await db.commit()
    resp = await client.put(
        "/api/v1/bale/custom-bot", json={"token": "777:shop-bale-bot"}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["custom_bot"] == {
        "username": "MahsaBaleBot",
        "active": True,
        "last_error": None,
        "link": "https://ble.ir/MahsaBaleBot",
    }
    [(webhook, host)] = [
        (c[2], h)
        for c, h in zip(fake_web.telegram.calls, fake_web.telegram.hosts, strict=True)
        if c[1] == "setWebhook"
    ]
    assert host == "bale.test"
    assert "?secret=" in webhook["url"]
    assert set(webhook) == {"url"}  # Bale takes only the URL
    # The Telegram page knows nothing about it: they are separate channels.
    telegram = (await client.get("/api/v1/telegram", headers=auth_headers)).json()
    assert telegram["custom_bot"] is None


async def test_panel_shows_bale(
    client: AsyncClient, auth_headers: dict, sessions: async_sessionmaker[AsyncSession]
) -> None:
    async with sessions() as db:
        db.add(
            TelegramBot(
                platform="bale",
                shop_id=None,
                bot_user_id=555,
                username="JavabBaleBot",
                webhook_secret="x",
                token_encrypted=encrypt_secret(BALE_TOKEN),
            )
        )
        await db.commit()
        shop = await db.scalar(select(Shop))
        assert shop is not None
        slug = shop.slug
    status = (await client.get("/api/v1/bale", headers=auth_headers)).json()
    assert status["available"] is True and status["enabled"] is True
    assert status["shared_bot_username"] == "JavabBaleBot"
    assert status["shop_link"] == f"https://ble.ir/JavabBaleBot?start=s_{slug}"
    assert status["shop_code"] == slug
    telegram = (await client.get("/api/v1/telegram", headers=auth_headers)).json()
    assert telegram["available"] is False  # Telegram itself isn't set up in this test
    link = (await client.post("/api/v1/bale/link", headers=auth_headers)).json()
    assert link["url"].startswith("https://ble.ir/JavabBaleBot?start=a_")
    dashboard = (await client.get("/api/v1/dashboard", headers=auth_headers)).json()
    assert dashboard["setup"]["bale_available"] is True


async def test_switches_are_separate(
    db: AsyncSession, setup: tuple[Shop, TelegramBot], fake_web: FakeWeb, queue: RecordingQueue
) -> None:
    """Turning Bale off doesn't touch Telegram, and the other way round."""
    shop, bot = setup
    shop.bale_enabled = False
    await db.commit()
    await _update(db, bot, fake_web, queue, _private(CUSTOMER, "/start s_mahsa"))
    await _update(db, bot, fake_web, queue, _private(CUSTOMER, "سلام"))
    assert queue.jobs == []  # Bale is off: no reply is scheduled
    assert shop.telegram_enabled is True

    shop.bale_enabled = True
    shop.telegram_enabled = False
    await db.commit()
    await _update(db, bot, fake_web, queue, _private(CUSTOMER, "قیمت؟"))
    assert [j.function for j in queue.jobs] == ["reply_conversation"]


async def test_panel_switch(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.patch("/api/v1/bale", json={"enabled": False}, headers=auth_headers)
    assert resp.json()["enabled"] is False
    telegram = (await client.get("/api/v1/telegram", headers=auth_headers)).json()
    assert telegram["enabled"] is True
