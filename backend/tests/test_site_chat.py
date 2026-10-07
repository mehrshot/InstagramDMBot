"""Javab's own assistant on the website: answers, daily allowance, the team taking over."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    Channel,
    Conversation,
    KnowledgeEntry,
    KnowledgeSection,
    Shop,
    TelegramBot,
    User,
)
from tests.conftest import FakeWeb, RecordingQueue
from tests.test_telegram import _private, _update, setup  # noqa: F401

VISITOR = str(uuid.uuid4())


@pytest.fixture
async def team(client: AsyncClient, db: AsyncSession) -> dict[str, str]:
    """The team's account, owning Javab's own shop (slug "javab")."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "team@javab.app", "password": "strongpass1", "shop_name": "جواب"},
    )
    shop = await db.scalar(select(Shop).join(User).where(User.email == "team@javab.app"))
    assert shop is not None
    shop.slug = get_settings().site_assistant_shop_slug
    shop.bot_enabled = True
    db.add(
        KnowledgeEntry(
            shop_id=shop.id, section=KnowledgeSection.ABOUT, content="جواب دستیار فروشگاه‌هاست"
        )
    )
    await db.commit()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _chat(client: AsyncClient, text: str, headers: dict | None = None):  # type: ignore[no-untyped-def]
    return await client.post(
        "/api/v1/site/chat", json={"visitor": VISITOR, "text": text}, headers=headers or {}
    )


async def test_not_set_up(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/site/chat", params={"visitor": VISITOR})).json()
    assert body["available"] is False
    assert (await _chat(client, "سلام")).status_code == 503


async def test_a_guest_asks_about_javab(
    client: AsyncClient, team: dict, fake_web: FakeWeb, llm_on: None, billing_on: None
) -> None:
    body = (await client.get("/api/v1/site/chat", params={"visitor": VISITOR})).json()
    assert body["available"] and body["messages"] == []
    assert body["quota"]["tier"] == "guest" and body["quota"]["left_percent"] == 100

    fake_web.llm_replies = [{"content": "جواب به پیام مشتری‌های فروشگاه شما جواب می‌دهد"}]
    resp = await _chat(client, "جواب چیکار میکنه؟")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [m["sender"] for m in body["messages"]] == ["customer", "bot"]
    quota = body["quota"]
    assert quota["used_tokens"] == 120 and quota["limit_tokens"] == 25_000
    assert quota["answers_left"] > 0
    # It knows our live prices and isn't charged to any wallet.
    system = fake_web.llm_requests[-1]["messages"][0]["content"]
    assert "CURRENT PRICES AND PLANS OF JAVAB" in system and "website chat" in system
    billing = (await client.get("/api/v1/billing", headers=team)).json()
    assert billing["balance_toman"] == 0

    # The chat shows up in the team's inbox like any conversation.
    inbox = (await client.get("/api/v1/conversations", headers=team)).json()
    assert inbox["items"][0]["channel"] == "web"


async def test_the_daily_allowance(
    client: AsyncClient,
    team: dict,
    fake_web: FakeWeb,
    llm_on: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "site_chat_guest_tokens", 150)
    assert (await _chat(client, "سلام")).status_code == 200  # 120 tokens of 150
    body = (await client.get("/api/v1/site/chat", params={"visitor": VISITOR})).json()
    assert body["quota"]["left_percent"] == 20 and body["quota"]["answers_left"] == 0
    assert (await _chat(client, "قیمت‌ها چنده؟")).status_code == 200  # still some left
    resp = await _chat(client, "و پلن‌ها؟")
    assert resp.status_code == 429 and "حساب" in resp.json()["detail"]
    body = (await client.get("/api/v1/site/chat", params={"visitor": VISITOR})).json()
    assert body["quota"]["exhausted"] == "personal" and body["quota"]["left_percent"] == 0

    # A new browser on the same network: its own allowance, until the network's runs out.
    monkeypatch.setattr(get_settings(), "site_chat_ip_tokens", 240)
    other = str(uuid.uuid4())
    resp = await client.post("/api/v1/site/chat", json={"visitor": other, "text": "سلام"})
    assert resp.status_code == 429  # 240 used from this IP already
    state = (await client.get("/api/v1/site/chat", params={"visitor": other})).json()
    assert state["quota"]["exhausted"] == "network"

    # Logging in gives the bigger, personal member allowance.
    member = await client.post(
        "/api/v1/auth/register",
        json={"email": "shop@owner.ir", "password": "strongpass1", "shop_name": "S"},
    )
    headers = {"Authorization": f"Bearer {member.json()['access_token']}"}
    resp = await _chat(client, "سلام", headers)
    assert resp.status_code == 200 and resp.json()["quota"]["tier"] == "member"


async def test_the_team_answers_what_the_bot_cannot(
    client: AsyncClient, team: dict, fake_web: FakeWeb, llm_on: None, db: AsyncSession
) -> None:
    fake_web.llm_replies = [
        FakeWeb.tool_call(
            "handoff_to_human",
            {"reason": "قرارداد سازمانی", "message": "سوالتان را به تیم دادم"},
        )
    ]
    body = (await _chat(client, "برای ۲۰ شعبه قرارداد سازمانی دارید؟")).json()
    assert body["waiting_for_team"] is True

    conversation = await db.scalar(select(Conversation).where(Conversation.channel == Channel.WEB))
    assert conversation is not None
    resp = await client.post(
        f"/api/v1/conversations/{conversation.id}/reply",
        json={"text": "بله، با هم صحبت کنیم 🌱"},
        headers=team,
    )
    assert resp.status_code == 200, resp.text
    body = (await client.get("/api/v1/site/chat", params={"visitor": VISITOR})).json()
    assert body["messages"][-1] == {**body["messages"][-1], "sender": "owner"}
    assert body["messages"][-1]["text"].startswith("بله، با هم")
    assert body["waiting_for_team"] is False


async def test_bad_input(client: AsyncClient, team: dict) -> None:
    resp = await client.post("/api/v1/site/chat", json={"visitor": "x" * 36, "text": "سلام"})
    assert resp.status_code == 400
    resp = await _chat(client, "ا" * 601)
    assert resp.status_code == 422


async def test_the_bot_without_a_shop_link_is_javabs_assistant(
    db: AsyncSession,
    setup: tuple[Shop, TelegramBot],  # noqa: F811
    fake_web: FakeWeb,
    queue: RecordingQueue,
) -> None:
    _, bot = setup
    owner = User(email="team@javab.app", password_hash="x")
    owner.shop = Shop(name="جواب", slug=get_settings().site_assistant_shop_slug, bot_enabled=True)
    db.add(owner)
    await db.commit()
    await _update(db, bot, fake_web, queue, _private(4242, "/start"))
    assert "دستیار هوشمند «جواب»" in fake_web.telegram.sent()[-1]["text"]
    await _update(db, bot, fake_web, queue, _private(4242, "قیمت جواب چنده؟"))
    conversation = await db.scalar(select(Conversation).where(Conversation.customer_id == "4242"))
    assert conversation is not None and conversation.shop_id == owner.shop.id
