import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeEntry, KnowledgeSection, Product, Shop
from app.services.llm import LLMClient, LLMError
from app.services.responder import ChatTurn, LLMResponder, history_to_messages
from tests.conftest import FakeWeb


@pytest.fixture
async def shop(db: AsyncSession) -> Shop:
    shop = Shop(
        owner_id=uuid.uuid4(),
        name="مزون مهسا",
        fallback_message="همکارم جواب میده",
        forbidden_rules="هیچ‌وقت تخفیف نده",
        use_emoji=False,
    )
    db.add(shop)
    await db.flush()
    db.add_all(
        [
            KnowledgeEntry(
                shop_id=shop.id, section=KnowledgeSection.SHIPPING, content="پست پیشتاز ۳ روزه"
            ),
            Product(
                shop_id=shop.id,
                name="مانتو کتان",
                color="مشکی",
                size="44",
                price=1250000,
                stock=3,
                extra={},
            ),
        ]
    )
    await db.commit()
    return shop


def _responder(db: AsyncSession, fake_web: FakeWeb) -> LLMResponder:
    return LLMResponder(LLMClient(fake_web.client()), db)


async def test_answers_from_product_lookup(
    db: AsyncSession, shop: Shop, fake_web: FakeWeb, llm_on
) -> None:
    fake_web.llm_replies = [
        FakeWeb.tool_call(
            "search_products", {"query": "مانتو کتان", "color": "مشکی", "size": "44"}
        ),
        {"content": "بله **موجوده**، قیمتش ۱,۲۵۰,۰۰۰ تومانه"},
    ]
    reply = await _responder(db, fake_web).generate(
        shop, [ChatTurn("customer", "سلام"), ChatTurn("customer", "مانتو کتان مشکی ۴۴ دارید؟")]
    )
    assert reply is not None
    assert reply.text == "بله موجوده، قیمتش ۱,۲۵۰,۰۰۰ تومانه"  # markdown stripped
    assert reply.unanswered is False
    assert reply.prompt_tokens == 200 and reply.completion_tokens == 40  # two LLM calls

    [lookup] = reply.tool_trace
    assert lookup["result"]["matches"][0]["price_toman"] == 1250000
    assert lookup["result"]["matches"][0]["in_stock"] is True

    first, second = fake_web.llm_requests
    system = first["messages"][0]["content"]
    assert "مزون مهسا" in system
    assert "پست پیشتاز ۳ روزه" in system
    assert "هیچ‌وقت تخفیف نده" in system
    assert "Never use emoji" in system
    # Consecutive customer messages are merged into one user turn.
    assert first["messages"][1] == {"role": "user", "content": "سلام\nمانتو کتان مشکی ۴۴ دارید؟"}
    assert {t["function"]["name"] for t in first["tools"]} == {
        "search_products",
        "handoff_to_human",
    }
    # The tool result is sent back to the model for the second call.
    assert second["messages"][-1]["role"] == "tool"
    assert "1250000" in second["messages"][-1]["content"]


async def test_missing_variant_suggests_others(
    db: AsyncSession, shop: Shop, fake_web: FakeWeb, llm_on
) -> None:
    fake_web.llm_replies = [
        FakeWeb.tool_call("search_products", {"query": "مانتو کتان", "color": "قرمز"}),
        {"content": "قرمزش رو نداریم، مشکیش هست"},
    ]
    reply = await _responder(db, fake_web).generate(shop, [ChatTurn("customer", "قرمز دارید؟")])
    assert reply is not None
    result = reply.tool_trace[0]["result"]
    assert result["matches"] == []
    assert result["same_product_other_variants"][0]["color"] == "مشکی"


async def test_handoff_sends_fallback_and_flags(
    db: AsyncSession, shop: Shop, fake_web: FakeWeb, llm_on
) -> None:
    fake_web.llm_replies = [FakeWeb.tool_call("handoff_to_human", {"reason": "asks for invoice"})]
    reply = await _responder(db, fake_web).generate(
        shop, [ChatTurn("customer", "فاکتور رسمی میدید؟")]
    )
    assert reply is not None
    assert reply.text == "همکارم جواب میده"
    assert reply.unanswered is True
    assert reply.handoff_reason == "asks for invoice"


async def test_no_product_tool_without_products(
    db: AsyncSession, fake_web: FakeWeb, llm_on
) -> None:
    shop = Shop(owner_id=uuid.uuid4(), name="بی‌محصول")
    db.add(shop)
    await db.commit()
    fake_web.llm_replies = [{"content": "سلام، در خدمتم"}]
    await _responder(db, fake_web).generate(shop, [ChatTurn("customer", "سلام")])
    tools = fake_web.llm_requests[0]["tools"]
    assert [t["function"]["name"] for t in tools] == ["handoff_to_human"]


async def test_endless_tool_calls_fall_back(
    db: AsyncSession, shop: Shop, fake_web: FakeWeb, llm_on
) -> None:
    fake_web.llm_replies = [FakeWeb.tool_call("search_products", {"query": "x"})] * 10
    reply = await _responder(db, fake_web).generate(shop, [ChatTurn("customer", "؟")])
    assert reply is not None and reply.unanswered
    assert len(fake_web.llm_requests) == 4  # capped


async def test_provider_errors(db: AsyncSession, shop: Shop, fake_web: FakeWeb, llm_on) -> None:
    fake_web.llm_status = 429
    with pytest.raises(LLMError) as busy:
        await _responder(db, fake_web).generate(shop, [ChatTurn("customer", "سلام")])
    assert busy.value.retryable
    fake_web.llm_status = 401
    with pytest.raises(LLMError) as rejected:
        await _responder(db, fake_web).generate(shop, [ChatTurn("customer", "سلام")])
    assert not rejected.value.retryable


def test_history_starts_with_customer() -> None:
    messages = history_to_messages(
        [ChatTurn("owner", "خوش اومدید"), ChatTurn("customer", "سلام"), ChatTurn("bot", "سلام!")]
    )
    assert [m["role"] for m in messages] == ["user", "assistant"]


async def test_playground(
    client: AsyncClient, auth_headers: dict, fake_web: FakeWeb, llm_on
) -> None:
    fake_web.llm_replies = [{"content": "ارسال با پست پیشتازه"}]
    resp = await client.post(
        "/api/v1/playground/chat",
        headers=auth_headers,
        json={"messages": [{"role": "customer", "text": "ارسال چجوریه؟"}]},
    )
    assert resp.status_code == 200
    assert resp.json()["reply"] == "ارسال با پست پیشتازه"
    assert resp.json()["ai_ready"] is True

    ends_with_bot = await client.post(
        "/api/v1/playground/chat",
        headers=auth_headers,
        json={"messages": [{"role": "bot", "text": "سلام"}]},
    )
    assert ends_with_bot.status_code == 422

    fake_web.llm_status = 500
    down = await client.post(
        "/api/v1/playground/chat",
        headers=auth_headers,
        json={"messages": [{"role": "customer", "text": "سلام"}]},
    )
    assert down.status_code == 502


async def test_playground_without_ai(client: AsyncClient, auth_headers: dict) -> None:
    resp = await client.post(
        "/api/v1/playground/chat",
        headers=auth_headers,
        json={"messages": [{"role": "customer", "text": "سلام"}]},
    )
    body = resp.json()
    assert body["ai_ready"] is False
    assert body["unanswered"] is True
