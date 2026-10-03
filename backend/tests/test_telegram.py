"""Telegram: customers through the shared bot, the owner's account, channels, Business."""

import uuid
from datetime import datetime
from itertools import count
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import encrypt_secret
from app.models import (
    Channel,
    Conversation,
    Message,
    MessageSender,
    Plan,
    Product,
    ProductOrigin,
    Shop,
    TelegramAdmin,
    TelegramBot,
    TelegramBusinessConnection,
    TelegramChannel,
    User,
)
from app.services import telegram_bot
from app.services.llm import LLMClient
from app.services.messaging import reply_to_conversation
from app.services.notify import TelegramNotifier
from app.services.responder import Reply
from app.services.telegram import TelegramClient
from tests.conftest import FakeWeb, RecordingQueue

SHARED_TOKEN = "111:shared-token"
OWNER = 5001
CUSTOMER = 7001
_ids = count(1)


class FixedResponder:
    def __init__(self, reply: Reply) -> None:
        self.reply = reply
        self.channels: list[Channel] = []

    async def generate(self, shop: Shop, history: list, *, channel: Channel, **_: Any) -> Reply:
        self.channels.append(channel)
        return self.reply


@pytest.fixture
async def setup(db: AsyncSession, fake_web: FakeWeb) -> tuple[Shop, TelegramBot]:
    fake_web.telegram.bots[SHARED_TOKEN] = {"id": 111, "username": "JavabBot", "first_name": "J"}
    user = User(email="owner@shop.ir", password_hash="x")
    user.shop = Shop(
        name="مزون مهسا", slug="mahsa123", bot_enabled=True, fallback_message="همکارم جواب میده"
    )
    bot = TelegramBot(
        shop_id=None,
        bot_user_id=111,
        username="JavabBot",
        webhook_secret="s3cret",
        token_encrypted=encrypt_secret(SHARED_TOKEN),
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


def _private(user_id: int, text: str = "", **extra: Any) -> dict[str, Any]:
    message = {
        "message_id": next(_ids),
        "date": int(datetime.now().timestamp()),
        "chat": {"id": user_id, "type": "private"},
        "from": {"id": user_id, "first_name": "Sara", "username": f"user{user_id}"},
        **extra,
    }
    if text:
        message["text"] = text
    return {"update_id": next(_ids), "message": message}


async def _update(db, bot, fake_web, queue, update) -> None:  # type: ignore[no-untyped-def]
    await telegram_bot.process_update(db, bot, update, _ctx(db, fake_web, queue))


async def _link_owner(db: AsyncSession, shop: Shop, bot: TelegramBot, fake_web, queue) -> None:
    from datetime import timedelta

    from app.core.timeutil import utcnow

    shop.telegram_link_code = "LINKCODE123"
    shop.telegram_link_expires_at = utcnow() + timedelta(minutes=5)
    await db.commit()
    await _update(db, bot, fake_web, queue, _private(OWNER, "/start a_LINKCODE123"))


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


async def test_webhook_checks_the_secret(
    client: AsyncClient, setup: tuple[Shop, TelegramBot], queue: RecordingQueue
) -> None:
    _, bot = setup
    url = f"/webhooks/telegram/{bot.id}"
    update = {"update_id": 9, "message": {"text": "hi"}}
    assert (await client.post(url, json=update)).status_code == 403
    resp = await client.post(
        url, json=update, headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"}
    )
    assert resp.status_code == 200
    [job] = queue.jobs
    assert job.function == "process_telegram_update" and job.job_id == f"tg:{bot.id}:9"


async def test_customer_comes_through_the_shop_link(
    db: AsyncSession, setup: tuple[Shop, TelegramBot], fake_web: FakeWeb, queue: RecordingQueue
) -> None:
    shop, bot = setup
    # Without a shop link the bot only explains itself (no AI call, nothing stored).
    await _update(db, bot, fake_web, queue, _private(CUSTOMER, "سلام"))
    assert "از لینکی" in fake_web.telegram.sent()[-1]["text"]
    assert queue.jobs == []

    await _update(db, bot, fake_web, queue, _private(CUSTOMER, "/start s_mahsa123"))
    assert "مزون مهسا" in fake_web.telegram.sent()[-1]["text"]
    await _update(db, bot, fake_web, queue, _private(CUSTOMER, "مانتو کتان دارید؟"))

    conversation = await db.scalar(select(Conversation))
    assert conversation is not None
    assert conversation.channel == Channel.TELEGRAM
    assert conversation.channel_ref == f"bot:{bot.id}"
    assert conversation.customer_id == str(CUSTOMER)
    assert conversation.customer_name == "Sara"

    responder = FixedResponder(Reply(text="بله، مشکی و سرمه‌ای داریم"))
    await _run_replies(db, queue, fake_web, responder)
    assert responder.channels == [Channel.TELEGRAM]
    answer = fake_web.telegram.sent()[-1]
    assert answer == {"chat_id": CUSTOMER, "text": "بله، مشکی و سرمه‌ای داریم"}
    bot_message = await db.scalar(select(Message).where(Message.sender == MessageSender.BOT))
    assert bot_message is not None and bot_message.external_id.startswith(f"tg:bot:{bot.id}:")


async def test_owner_gets_handoffs_and_answers_from_telegram(
    db: AsyncSession, setup: tuple[Shop, TelegramBot], fake_web: FakeWeb, queue: RecordingQueue
) -> None:
    shop, bot = setup
    await _link_owner(db, shop, bot, fake_web, queue)
    admin = await db.scalar(select(TelegramAdmin))
    assert admin is not None and admin.shop_id == shop.id and admin.telegram_user_id == OWNER
    await db.refresh(shop)
    assert shop.telegram_link_code is None  # single use

    await _update(db, bot, fake_web, queue, _private(CUSTOMER, "/start s_mahsa123"))
    await _update(db, bot, fake_web, queue, _private(CUSTOMER, "فاکتور رسمی می‌دید؟"))
    await _run_replies(
        db,
        queue,
        fake_web,
        FixedResponder(
            Reply(text="از همکارم می‌پرسم", unanswered=True, handoff_reason="فاکتور رسمی")
        ),
    )
    alert = [m for m in fake_web.telegram.sent() if m["chat_id"] == OWNER][-1]
    assert "فاکتور رسمی می‌دید؟" in alert["text"] and "Sara" in alert["text"]
    conversation = await db.scalar(select(Conversation))
    assert conversation is not None
    buttons = [b["callback_data"] for row in alert["reply_markup"]["inline_keyboard"] for b in row]
    assert f"reply:{conversation.id}" in buttons

    await _update(
        db,
        bot,
        fake_web,
        queue,
        {
            "update_id": next(_ids),
            "callback_query": {
                "id": "cb1",
                "from": {"id": OWNER},
                "data": f"reply:{conversation.id}",
                "message": {"message_id": 1, "chat": {"id": OWNER}},
            },
        },
    )
    await _update(db, bot, fake_web, queue, _private(OWNER, "بله، با کد اقتصادی"))
    to_customer = [m for m in fake_web.telegram.sent() if m["chat_id"] == CUSTOMER][-1]
    assert to_customer["text"] == "بله، با کد اقتصادی"
    await db.refresh(conversation)
    assert not conversation.handoff_open and conversation.bot_paused_until is not None
    owner_message = await db.scalar(select(Message).where(Message.sender == MessageSender.OWNER))
    assert owner_message is not None and owner_message.text == "بله، با کد اقتصادی"


async def test_owner_teaches_by_text_and_confirms(
    db: AsyncSession,
    setup: tuple[Shop, TelegramBot],
    fake_web: FakeWeb,
    queue: RecordingQueue,
    llm_on: None,
) -> None:
    shop, bot = setup
    await _link_owner(db, shop, bot, fake_web, queue)
    fake_web.llm_replies.append(
        FakeWeb.tool_call(
            "propose_changes",
            {
                "summary": "یک محصول جدید",
                "products": [{"name": "کیف چرم", "price_toman": 1900000, "stock": 2}],
            },
        )
    )
    await _update(db, bot, fake_web, queue, _private(OWNER, "کیف چرم دارم یک و نهصد، دو تا"))
    preview = fake_web.telegram.sent()[-1]
    assert "➕ کیف چرم" in preview["text"]
    apply = preview["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    assert apply.startswith("apply:")
    assert await db.scalar(select(Product)) is None  # nothing changes before the OK

    await _update(
        db,
        bot,
        fake_web,
        queue,
        {
            "update_id": next(_ids),
            "callback_query": {
                "id": "cb2",
                "from": {"id": OWNER},
                "data": apply,
                "message": {"message_id": 3, "chat": {"id": OWNER}},
            },
        },
    )
    product = await db.scalar(select(Product))
    assert product is not None and product.name == "کیف چرم" and product.stock == 2
    assert "1 محصول اضافه شد" in fake_web.telegram.sent()[-1]["text"]


async def test_owner_voice_note(
    db: AsyncSession,
    setup: tuple[Shop, TelegramBot],
    fake_web: FakeWeb,
    queue: RecordingQueue,
    llm_on: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    shop, bot = setup
    db.add(Product(shop_id=shop.id, name="مانتو کتان", color="مشکی", stock=3, extra={}))
    await db.commit()
    await _link_owner(db, shop, bot, fake_web, queue)
    voice = {"file_id": "VOICE1", "duration": 4}
    await _update(db, bot, fake_web, queue, _private(OWNER, voice=voice))
    assert "پیام صوتی" in fake_web.telegram.sent()[-1]["text"]  # no speech model configured

    monkeypatch.setattr(get_settings(), "llm_transcribe_model", "whisper-1")
    fake_web.llm_replies.append(
        FakeWeb.tool_call(
            "propose_changes",
            {
                "summary": "مانتو مشکی تمام شد",
                "products": [{"ref": "#1", "stock": 0}],
            },
        )
    )
    await _update(db, bot, fake_web, queue, _private(OWNER, voice=voice))
    texts = [m["text"] for m in fake_web.telegram.sent()]
    assert any("مانتو کتان مشکی تموم شد" in t for t in texts)  # the transcript is echoed
    assert "موجودی: 3 ← 0" in texts[-1]


async def test_channel_posts_become_products(
    db: AsyncSession,
    setup: tuple[Shop, TelegramBot],
    fake_web: FakeWeb,
    queue: RecordingQueue,
    llm_on: None,
) -> None:
    shop, bot = setup
    await _link_owner(db, shop, bot, fake_web, queue)
    channel_chat = {"id": -1001234, "type": "channel", "title": "مزون", "username": "mahsa_shop"}
    await _update(
        db,
        bot,
        fake_web,
        queue,
        {
            "update_id": next(_ids),
            "my_chat_member": {
                "chat": channel_chat,
                "from": {"id": OWNER},
                "new_chat_member": {"status": "administrator"},
            },
        },
    )
    channel = await db.scalar(select(TelegramChannel))
    assert channel is not None and channel.shop_id == shop.id and channel.is_active

    fake_web.llm_replies.append(
        FakeWeb.tool_call(
            "propose_changes",
            {
                "summary": "یک شومیز",
                "products": [{"name": "شومیز حریر", "price_toman": 890000}],
                "knowledge": [{"section": "free_text", "content": "posts don't teach policies"}],
            },
        )
    )
    await _update(
        db,
        bot,
        fake_web,
        queue,
        {
            "update_id": next(_ids),
            "channel_post": {
                "message_id": 77,
                "chat": channel_chat,
                "date": 1_790_000_000,
                "caption": "شومیز حریر ۸۹۰",
                "photo": [{"file_id": "small"}, {"file_id": "BIG"}],
            },
        },
    )
    product = await db.scalar(select(Product))
    assert product is not None and product.origin == ProductOrigin.TELEGRAM_POST
    assert product.telegram_post_id is not None
    notice = [m for m in fake_web.telegram.sent() if m["chat_id"] == OWNER][-1]
    assert "شومیز حریر" in notice["text"]
    assert notice["reply_markup"]["inline_keyboard"][0][0]["callback_data"].startswith("undo:")

    # When the bot recommends it, the customer gets the channel post itself.
    from app.services.posts import shareable_posts

    links = await shareable_posts(db, shop.id, Channel.TELEGRAM, [product])
    assert links["شومیز حریر"].permalink == "https://t.me/mahsa_shop/77"
    assert links["شومیز حریر"].photo == "BIG"


async def test_telegram_business(
    db: AsyncSession, setup: tuple[Shop, TelegramBot], fake_web: FakeWeb, queue: RecordingQueue
) -> None:
    shop, bot = setup
    await _link_owner(db, shop, bot, fake_web, queue)
    connection_update = {
        "update_id": next(_ids),
        "business_connection": {
            "id": "BIZ1",
            "user": {"id": OWNER},
            "user_chat_id": OWNER,
            "is_enabled": True,
            "rights": {"can_reply": True},
        },
    }
    await _update(db, bot, fake_web, queue, connection_update)
    assert "پلن «بیزینس»" in fake_web.telegram.sent()[-1]["text"]  # basic plan: a warning
    connection = await db.scalar(select(TelegramBusinessConnection))
    assert connection is not None and connection.shop_id == shop.id

    def business(sender: int, text: str) -> dict[str, Any]:
        return {
            "update_id": next(_ids),
            "business_message": {
                "business_connection_id": "BIZ1",
                "message_id": next(_ids),
                "date": int(datetime.now().timestamp()),
                "chat": {"id": CUSTOMER, "type": "private", "first_name": "Ali"},
                "from": {"id": sender},
                "text": text,
            },
        }

    await _update(db, bot, fake_web, queue, business(CUSTOMER, "قیمت؟"))
    responder = FixedResponder(Reply(text="۸۹۰ هزار تومان"))
    await _run_replies(db, queue, fake_web, responder)
    assert not [m for m in fake_web.telegram.sent() if m.get("business_connection_id")]

    shop.plan = Plan.BUSINESS
    await db.commit()
    await _update(db, bot, fake_web, queue, business(CUSTOMER, "قیمت شومیز؟"))
    await _run_replies(db, queue, fake_web, responder)
    [answer] = [m for m in fake_web.telegram.sent() if m.get("business_connection_id")]
    assert answer == {
        "chat_id": CUSTOMER,
        "text": "۸۹۰ هزار تومان",
        "business_connection_id": "BIZ1",
    }

    # The owner writing in the chat themselves makes the bot step back.
    await _update(db, bot, fake_web, queue, business(OWNER, "سلام علی جان، خودم هستم"))
    conversation = await db.scalar(select(Conversation))
    assert conversation is not None and conversation.channel_ref == f"biz:{connection.id}"
    assert conversation.bot_paused_until is not None


async def test_custom_bot_needs_a_paid_plan(
    client: AsyncClient,
    auth_headers: dict,
    fake_web: FakeWeb,
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    fake_web.telegram.bots["222:shop-bot-token"] = {
        "id": 222,
        "username": "MahsaShopBot",
        "first_name": "Mahsa",
    }
    body = {"token": "222:shop-bot-token"}
    resp = await client.put("/api/v1/telegram/custom-bot", json=body, headers=auth_headers)
    assert resp.status_code == 422 and "حرفه‌ای" in resp.json()["detail"]

    async with sessions() as db:
        shop = await db.scalar(select(Shop))
        assert shop is not None
        shop.plan = Plan.PRO
        await db.commit()
    resp = await client.put("/api/v1/telegram/custom-bot", json=body, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["custom_bot"]["username"] == "MahsaShopBot"
    [(token, _, webhook)] = [c for c in fake_web.telegram.calls if c[1] == "setWebhook"]
    assert token == "222:shop-bot-token"
    assert webhook["url"].startswith("https://api.test/webhooks/telegram/")
    assert "business_message" in webhook["allowed_updates"]

    resp = await client.put(
        "/api/v1/telegram/custom-bot", json={"token": "333:wrong-token-x"}, headers=auth_headers
    )
    assert resp.status_code == 422 and "نامعتبر" in resp.json()["detail"]


async def test_panel_status_and_owner_link(
    client: AsyncClient,
    auth_headers: dict,
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    status = (await client.get("/api/v1/telegram", headers=auth_headers)).json()
    assert status["available"] is False and status["shop_link"] is None
    assert (await client.post("/api/v1/telegram/link", headers=auth_headers)).status_code == 503

    async with sessions() as db:
        db.add(
            TelegramBot(
                shop_id=None,
                bot_user_id=111,
                username="JavabBot",
                webhook_secret="x",
                token_encrypted=encrypt_secret(SHARED_TOKEN),
            )
        )
        await db.commit()
        shop = await db.scalar(select(Shop))
        assert shop is not None
        slug = shop.slug
    status = (await client.get("/api/v1/telegram", headers=auth_headers)).json()
    assert status["shop_link"] == f"https://t.me/JavabBot?start=s_{slug}"
    link = (await client.post("/api/v1/telegram/link", headers=auth_headers)).json()
    assert link["url"].startswith("https://t.me/JavabBot?start=a_")


async def test_owner_replies_from_the_panel(
    client: AsyncClient,
    auth_headers: dict,
    fake_web: FakeWeb,
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    fake_web.telegram.bots[SHARED_TOKEN] = {"id": 111, "username": "JavabBot", "first_name": "J"}
    async with sessions() as db:
        shop = await db.scalar(select(Shop))
        assert shop is not None
        bot = TelegramBot(
            shop_id=None,
            bot_user_id=111,
            username="JavabBot",
            webhook_secret="x",
            token_encrypted=encrypt_secret(SHARED_TOKEN),
        )
        db.add(bot)
        await db.flush()
        conversation = Conversation(
            shop_id=shop.id,
            channel=Channel.TELEGRAM,
            channel_ref=f"bot:{bot.id}",
            customer_id=str(CUSTOMER),
        )
        db.add(conversation)
        await db.commit()
        conversation_id = conversation.id
    resp = await client.post(
        f"/api/v1/conversations/{conversation_id}/reply",
        json={"text": "سلام، بله"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["channel"] == "telegram" and resp.json()["bot_paused"]
    assert fake_web.telegram.sent()[-1] == {"chat_id": CUSTOMER, "text": "سلام، بله"}


def test_display_text() -> None:
    assert telegram_bot.display_text({"photo": [{}], "caption": "این چنده؟"}) == "این چنده؟ [photo]"
    assert telegram_bot.display_text({"sticker": {"emoji": "😍"}}) == "[sticker 😍]"
    assert telegram_bot.display_text({}) == "[message]"


async def test_plan_gating_of_endpoints(db: AsyncSession) -> None:
    from app.services.channels import plan_allows

    shop = Shop(name="s", plan=Plan.BASIC)
    custom = TelegramBot(shop_id=uuid.uuid4())
    assert plan_allows(shop, "bot:x", TelegramBot(shop_id=None))
    assert not plan_allows(shop, "bot:x", custom)
    assert not plan_allows(shop, "biz:x")
    shop.plan = Plan.PRO
    assert plan_allows(shop, "bot:x", custom) and not plan_allows(shop, "biz:x")


async def test_owner_chat_is_a_conversation(
    db: AsyncSession,
    setup: tuple[Shop, TelegramBot],
    fake_web: FakeWeb,
    queue: RecordingQueue,
    llm_on: None,
) -> None:
    """A follow-up refines the waiting proposal, and later messages know what came before."""
    from app.models import ProposalStatus, TeachProposal

    shop, bot = setup
    await _link_owner(db, shop, bot, fake_web, queue)
    first = "محصول جدیدمون کفش پاشنه بلنده که فقط ۳ تا ازش داریم تو سایز ۴۲ و رنگ مشکی"
    fake_web.llm_replies.append(
        FakeWeb.tool_call(
            "propose_changes",
            {
                "summary": "یک کفش؛ قیمت اعلام نشده",
                "products": [{"name": "کفش پاشنه‌بلند", "color": "مشکی", "size": "42", "stock": 3}],
            },
        )
    )
    await _update(db, bot, fake_web, queue, _private(OWNER, first))
    first_preview = fake_web.telegram.sent()[-1]
    assert "reply_markup" in first_preview

    # "Its price is 2.5 million": read together with the waiting proposal, which it replaces.
    fake_web.llm_replies.append(
        FakeWeb.tool_call(
            "propose_changes",
            {
                "summary": "کفش با قیمت ۲٬۵۰۰٬۰۰۰ تومان",
                "products": [
                    {
                        "name": "کفش پاشنه‌بلند",
                        "color": "مشکی",
                        "size": "42",
                        "stock": 3,
                        "price_toman": 2500000,
                    }
                ],
            },
        )
    )
    await _update(db, bot, fake_web, queue, _private(OWNER, "قیمتش رو بذار دو و پونصد"))
    request = fake_web.llm_requests[-1]["messages"]
    assert first in request[1]["content"] and "دو و پونصد" in request[1]["content"]
    assert "Owner: " + first in request[0]["content"]  # the conversation so far
    proposals = (await db.scalars(select(TeachProposal).order_by(TeachProposal.created_at))).all()
    assert [p.status for p in proposals] == [ProposalStatus.DISCARDED, ProposalStatus.PENDING]
    assert proposals[1].changes["products"][0]["fields"]["price"] == 2500000
    # The old preview lost its buttons, so only the new one can be saved.
    assert any(m == "editMessageReplyMarkup" for _, m, _ in fake_web.telegram.calls)

    apply = fake_web.telegram.sent()[-1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    await _update(
        db,
        bot,
        fake_web,
        queue,
        {
            "update_id": next(_ids),
            "callback_query": {
                "id": "cb9",
                "from": {"id": OWNER},
                "data": apply,
                "message": {"message_id": 9, "chat": {"id": OWNER}},
            },
        },
    )
    product = await db.scalar(select(Product))
    assert product is not None and product.price == 2500000

    # Later: "make it 3 million" is understood from the conversation (no proposal waiting).
    fake_web.llm_replies.append(FakeWeb.tool_call("propose_changes", {"summary": "ok"}))
    await _update(db, bot, fake_web, queue, _private(OWNER, "قیمتش رو کن سه میلیون"))
    system = fake_web.llm_requests[-1]["messages"][0]["content"]
    assert "You: ✅ ثبت شد" in system or "You: ثبت شد" in system
    assert fake_web.llm_requests[-1]["messages"][1]["content"] == "قیمتش رو کن سه میلیون"
