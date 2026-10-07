"""Questions unrelated to the shop: a cheap check, a canned reply, no charge, then silence."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Message, MessageSender, Shop, TelegramBot, WalletEntry
from app.services.llm import LLMClient
from app.services.responder import ChatTurn, LLMResponder, Reply, looks_on_topic
from tests.conftest import FakeWeb, RecordingQueue
from tests.test_responder import shop  # noqa: F401
from tests.test_telegram import (  # noqa: F401
    CUSTOMER,
    FixedResponder,
    _private,
    _run_replies,
    _update,
    setup,
)


@pytest.fixture
def guard_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "off_topic_guard", True)


def _responder(db: AsyncSession, fake_web: FakeWeb) -> LLMResponder:
    return LLMResponder(LLMClient(fake_web.client()), db)


async def test_unrelated_question_gets_the_canned_reply(
    db: AsyncSession,
    shop: Shop,  # noqa: F811
    fake_web: FakeWeb,
    llm_on: None,
    guard_on: None,
) -> None:
    fake_web.llm_replies = [FakeWeb.tool_call("classify", {"topic": "off_topic"})]
    reply = await _responder(db, fake_web).generate(
        shop, [ChatTurn("customer", "هوای امروز تهران چطوره؟")]
    )
    assert reply is not None and reply.off_topic
    assert "مزون مهسا" in reply.text and "محصولات" in reply.text
    # Only the small check ran: no full answer with the shop's information.
    assert len(fake_web.llm_requests) == 1
    check = fake_web.llm_requests[0]
    assert check["tool_choice"]["function"]["name"] == "classify"
    assert "SHOP INFORMATION" not in check["messages"][0]["content"]
    assert reply.prompt_tokens == 100  # the check's tokens are still recorded


async def test_english_and_formal_wording(shop: Shop) -> None:  # noqa: F811
    from app.services.responder import off_topic_text

    assert "only help" in off_topic_text(shop, "what's the weather like?")
    shop.tone = "formal"
    assert "می‌توانم" in off_topic_text(shop, "هوا چطوره")


async def test_shopping_questions_skip_the_check(
    db: AsyncSession,
    shop: Shop,  # noqa: F811
    fake_web: FakeWeb,
    llm_on: None,
    guard_on: None,
) -> None:
    fake_web.llm_replies = [{"content": "بله موجوده"}]
    reply = await _responder(db, fake_web).generate(
        shop, [ChatTurn("customer", "مانتو کتان مشکی هنوز هست؟")]
    )
    assert reply is not None and not reply.off_topic
    assert len(fake_web.llm_requests) == 1
    assert "SHOP INFORMATION" in fake_web.llm_requests[0]["messages"][0]["content"]


async def test_unclear_questions_get_a_full_answer(
    db: AsyncSession,
    shop: Shop,  # noqa: F811
    fake_web: FakeWeb,
    llm_on: None,
    guard_on: None,
) -> None:
    fake_web.llm_replies = [
        FakeWeb.tool_call("classify", {"topic": "shop"}),
        {"content": "سه روز کاری"},
    ]
    reply = await _responder(db, fake_web).generate(
        shop, [ChatTurn("customer", "کی به دستم می‌رسه؟")]
    )
    assert reply is not None and reply.text == "سه روز کاری" and not reply.off_topic
    assert reply.prompt_tokens == 200  # the check and the answer


def test_keywords() -> None:
    assert looks_on_topic("قیمتش چنده؟", [])
    assert looks_on_topic("do you ship to Shiraz?", [])
    assert not looks_on_topic("هوای تهران امروز چطوره", [])


async def test_canned_replies_are_free_then_the_bot_goes_quiet(
    db: AsyncSession,
    setup: tuple[Shop, TelegramBot],  # noqa: F811
    fake_web: FakeWeb,
    queue: RecordingQueue,
    billing_on: None,
) -> None:
    the_shop, bot = setup
    the_shop.balance_rial = 1_000_000
    await db.commit()
    responder = FixedResponder(
        Reply(text="فقط درباره‌ی فروشگاه", off_topic=True, prompt_tokens=90, completion_tokens=5)
    )
    await _update(db, bot, fake_web, queue, _private(CUSTOMER, "/start s_mahsa123"))
    for question in ("هوا چطوره", "یه جوک بگو", "پایتخت فرانسه کجاست"):
        await _update(db, bot, fake_web, queue, _private(CUSTOMER, question))
        await _run_replies(db, queue, fake_web, responder)

    bot_messages = (
        await db.scalars(select(Message).where(Message.sender == MessageSender.BOT))
    ).all()
    assert [m.off_topic for m in bot_messages] == [True, True]  # the third got no reply
    assert len(responder.channels) == 2  # and no AI call at all
    assert (await db.scalars(select(WalletEntry))).all() == []  # never charged

    # A shopping question brings the bot back.
    responder.reply = Reply(text="بله موجوده", prompt_tokens=4000, completion_tokens=150)
    await _update(db, bot, fake_web, queue, _private(CUSTOMER, "قیمت مانتو چنده؟"))
    await _run_replies(db, queue, fake_web, responder)
    last = (await db.scalars(select(Message).order_by(Message.created_at.desc()).limit(1))).one()
    assert last.text == "بله موجوده" and not last.off_topic
    assert len((await db.scalars(select(WalletEntry))).all()) == 1
