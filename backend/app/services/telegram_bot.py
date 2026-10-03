"""What our Telegram and Bale bots do with each update.

One handler serves every bot (the shared Javab bots and shops' custom bots), on both apps:
Bale's Bot API is a copy of Telegram's, minus Business connections and channel updates.

Customers
- shared bot: the shop's start link (?start=s_<slug>) remembers which shop they came for;
  from then on their messages go to that shop's assistant.
- custom bot: the bot belongs to one shop, so every private message is for it.
- Telegram Business: the owner connected a bot to their own account; their customers' private
  messages arrive as business messages and the bot answers on the owner's behalf. The owner's
  own messages in those chats pause the bot, like a manual reply on Instagram.

The owner (a linked Telegram account, see /start a_<code>)
- gets alerts with buttons (answer the customer from here, close, silence the bot);
- teaches the bot by typing, sending a voice note, a file, a photo, a Google link or a
  forwarded channel post; every such input becomes a proposal they confirm with a button;
- adds the bot as an admin of their channel, after which new product posts are added to the
  catalogue automatically (with an undo button).
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.queue import Queue
from app.core.security import decrypt_secret
from app.core.timeutil import as_utc, utcnow
from app.models import (
    Channel,
    Conversation,
    HandoffResolution,
    Product,
    ProductOrigin,
    ProposalStatus,
    Shop,
    TeachProposal,
    TelegramAdmin,
    TelegramBot,
    TelegramBusinessConnection,
    TelegramChannel,
    TelegramPost,
    TelegramSession,
)
from app.services import billing, messaging, teach
from app.services.channels import (
    PLANS_FOR_BUSINESS,
    Gateways,
    SendError,
    bot_ref,
    business_ref,
    sender_for,
    split_text,
    telegram_message_key,
)
from app.services.instagram import InstagramClient
from app.services.llm import LLMClient, LLMError
from app.services.notify import Notifier, customer_label, inline_keyboard
from app.services.telegram import MAX_TEXT_LENGTH, TelegramClient, TelegramError

logger = logging.getLogger(__name__)

LINK_CODE_LIFETIME = timedelta(minutes=30)
# The owner's chat with the bot is a conversation: the last turns are given to the AI, and a
# message sent while a proposal still waits for the OK refines that proposal.
HISTORY_TURNS = 8
FOLLOW_UP_WINDOW = timedelta(minutes=30)
# Voice notes and files the owner sends; Telegram's own bot download limit is 20 MB.
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024

BUTTON_PRODUCTS = "📦 محصولات"
BUTTON_WALLET = "💰 کیف پول"
BUTTON_PAUSE = "⏸ خاموش کردن ربات"
BUTTON_RESUME = "▶️ روشن کردن ربات"
BUTTON_TEST = "🧪 تست به‌عنوان مشتری"
BUTTON_HELP = "❓ راهنما"

ADMIN_HELP = """من «جواب» هستم، دستیار هوشمند فروشگاه شما 🤝

برای اینکه محصولات و اطلاعات فروشگاه را یاد بگیرم، هر جور راحت‌ترید به من بگویید:
• تایپ کنید: «مانتو کتان مشکی سایز ۴۴، یک و دویست، ۳ تا موجوده»
• پیام صوتی بفرستید و توضیح بدهید
• لینک گوگل شیت، گوگل داک یا فایل گوگل درایو بفرستید
• فایل PDF، Word یا Excel لیست قیمت را بفرستید
• عکس محصول با توضیح زیرش، یا عکس لیست قیمت بفرستید
• پست‌های کانال‌تان را برایم فوروارد کنید
• تغییرها را هم همین‌طور بگویید: «مانتو کتان تموم شد» یا «قیمت شومیز حریر شد ۹۵۰»

هر بار قبل از ثبت، خلاصه‌ی چیزی که فهمیدم را نشانتان می‌دهم تا تأیید کنید.

{channel}🔔 وقتی مشتری‌ای منتظر جواب شما باشد، همین‌جا خبرتان می‌کنم و می‌توانید از همین‌جا جوابش را بدهید."""


@dataclass
class BotContext:
    client: TelegramClient
    llm: LLMClient
    http: httpx.AsyncClient
    queue: Queue
    notifier: Notifier
    debounce_seconds: float


class _Bot:
    """One update being handled by one of our bots."""

    def __init__(self, db: AsyncSession, bot: TelegramBot, ctx: BotContext) -> None:
        self.db = db
        self.bot = bot
        self.ctx = ctx
        self.client = ctx.client.for_platform(bot.platform)
        self.channel = Channel.BALE if bot.platform == "bale" else Channel.TELEGRAM
        self.token = decrypt_secret(bot.token_encrypted)

    async def send(
        self, chat_id: int, text: str, keyboard: dict[str, Any] | None = None
    ) -> int | None:
        message_id = None
        chunks = split_text(text, MAX_TEXT_LENGTH) or [text]
        for index, chunk in enumerate(chunks):
            try:
                message_id = await self.client.send_message(
                    self.token,
                    chat_id,
                    chunk,
                    reply_markup=keyboard if index == len(chunks) - 1 else None,
                    disable_preview=True,
                )
            except TelegramError as exc:
                logger.info("telegram send to %s failed: %s", chat_id, exc)
                return None
        return message_id

    async def typing(self, chat_id: int) -> None:
        try:
            await self.client.send_chat_action(self.token, chat_id)
        except TelegramError:
            pass


async def process_update(
    db: AsyncSession, bot: TelegramBot, update: dict[str, Any], ctx: BotContext
) -> None:
    if not bot.is_active:
        return
    handler = _Bot(db, bot, ctx)
    try:
        if "message" in update:
            await _on_private_message(handler, update["message"])
        elif "callback_query" in update:
            await _on_callback(handler, update["callback_query"])
        elif "my_chat_member" in update:
            await _on_membership(handler, update["my_chat_member"])
        elif "channel_post" in update:
            await _on_channel_post(handler, update["channel_post"], edited=False)
        elif "edited_channel_post" in update:
            await _on_channel_post(handler, update["edited_channel_post"], edited=True)
        elif "business_connection" in update:
            await _on_business_connection(handler, update["business_connection"])
        elif "business_message" in update:
            await _on_business_message(handler, update["business_message"])
    except LLMError as exc:
        if exc.retryable:
            raise
        logger.error("LLM rejected a request while handling a telegram update: %s", exc)


# ---------------------------------------------------------------------------- private chats


async def _on_private_message(h: _Bot, message: dict[str, Any]) -> None:
    chat = message.get("chat") or {}
    user = message.get("from") or {}
    if chat.get("type") != "private" or not user.get("id") or user.get("is_bot"):
        return
    user_id = int(user["id"])
    chat_id = int(chat["id"])
    text = (message.get("text") or message.get("caption") or "").strip()
    session = await _session(h, user_id)
    admin = await _admin_for(h, user_id)

    if text.startswith("/start"):
        param = text.removeprefix("/start").strip()
        await _on_start(h, session, admin, user, chat_id, param)
        return
    if admin is not None:
        command = _command(text)
        if command == "/admin":
            session.mode = "admin"
            session.state = {}
            await h.db.commit()
            await _send_admin_menu(h, chat_id, admin)
            return
        if command in ("/test", "/customer") or text == BUTTON_TEST:
            session.mode = "customer"
            session.shop_id = admin.shop_id
            session.state = {}
            await h.db.commit()
            await h.send(
                chat_id,
                "حالا مثل یک مشتری پیام بدهید تا جواب ربات را ببینید. "
                "برای برگشتن به مدیریت /admin را بزنید.",
                {"remove_keyboard": True},
            )
            return
        if session.mode == "admin":
            await _on_admin_message(h, session, admin, message, chat_id, text)
            return

    await _on_customer_message(h, session, message, user, chat_id)


async def _on_start(
    h: _Bot,
    session: TelegramSession,
    admin: TelegramAdmin | None,
    user: dict[str, Any],
    chat_id: int,
    param: str,
) -> None:
    if param.startswith("a_") and h.bot.is_shared:
        await _link_owner(h, session, user, chat_id, param.removeprefix("a_"))
        return
    if param.startswith("s_") and h.bot.is_shared:
        shop = await h.db.scalar(select(Shop).where(Shop.slug == param.removeprefix("s_")))
        if shop is None:
            await h.send(chat_id, "این لینک معتبر نیست. لینک فروشگاه را دوباره از خودش بگیرید.")
            return
        session.shop_id = shop.id
        session.mode = "customer"
        session.state = {}
        await h.db.commit()
        await h.send(chat_id, _welcome(shop))
        return
    if h.bot.shop_id is not None:
        shop = await h.db.get(Shop, h.bot.shop_id)
        if shop is not None:
            await h.send(chat_id, _welcome(shop))
        return
    if admin is not None:
        session.mode = "admin"
        session.state = {}
        await h.db.commit()
        await _send_admin_menu(h, chat_id, admin)
        return
    if session.shop_id is not None:
        shop = await h.db.get(Shop, session.shop_id)
        if shop is not None:
            await h.send(chat_id, _welcome(shop))
            return
    await h.send(
        chat_id,
        "سلام! 👋 این ربات «جواب» است؛ دستیار هوشمند فروشگاه‌های آنلاین.\n\n"
        "• اگر مشتری یک فروشگاه هستید، از لینکی که فروشگاه گذاشته وارد شوید.\n"
        f"• اگر صاحب فروشگاه هستید، از پنل «جواب» ({get_settings().frontend_url}) "
        "بخش تلگرام، حسابتان را وصل کنید.",
    )


def _welcome(shop: Shop) -> str:
    if not shop.bot_enabled:
        return (
            f"سلام! به «{shop.name}» خوش آمدید. پیامتان را بنویسید تا همکاران فروشگاه جواب بدهند."
        )
    return (
        f"سلام! 👋 من دستیار هوشمند «{shop.name}» هستم. هر سوالی درباره‌ی محصولات، قیمت، "
        "موجودی، ارسال یا نحوه‌ی خرید دارید بپرسید."
    )


async def _link_owner(
    h: _Bot, session: TelegramSession, user: dict[str, Any], chat_id: int, code: str
) -> None:
    shop = await h.db.scalar(select(Shop).where(Shop.telegram_link_code == code)) if code else None
    expires = shop.telegram_link_expires_at if shop else None
    if shop is None or expires is None or as_utc(expires) < utcnow():
        await h.send(chat_id, "این لینک اتصال منقضی شده است. از پنل «جواب» یک لینک تازه بسازید.")
        return
    user_id = int(user["id"])
    admin = await h.db.scalar(
        select(TelegramAdmin).where(
            TelegramAdmin.platform == h.bot.platform, TelegramAdmin.telegram_user_id == user_id
        )
    )
    if admin is None:
        admin = TelegramAdmin(platform=h.bot.platform, telegram_user_id=user_id, shop_id=shop.id)
        h.db.add(admin)
    admin.shop_id = shop.id
    admin.username = (user.get("username") or "")[:64] or None
    admin.first_name = (user.get("first_name") or "")[:128]
    admin.notify = True
    shop.telegram_link_code = None
    shop.telegram_link_expires_at = None
    session.mode = "admin"
    session.state = {}
    await h.db.commit()
    app = "بله" if h.bot.platform == "bale" else "تلگرام"
    await h.send(chat_id, f"✅ حساب {app} شما به فروشگاه «{shop.name}» وصل شد.")
    await _send_admin_menu(h, chat_id, admin)


def _admin_keyboard(shop: Shop) -> dict[str, Any]:
    toggle = BUTTON_PAUSE if shop.bot_enabled else BUTTON_RESUME
    return {
        "keyboard": [
            [{"text": BUTTON_PRODUCTS}, {"text": BUTTON_WALLET}],
            [{"text": toggle}, {"text": BUTTON_TEST}],
            [{"text": BUTTON_HELP}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


async def _send_admin_menu(h: _Bot, chat_id: int, admin: TelegramAdmin) -> None:
    shop = await h.db.get(Shop, admin.shop_id)
    if shop is None:
        return
    state = "روشن ✅" if shop.bot_enabled else "خاموش ⏸"
    await h.send(
        chat_id, f"مدیریت «{shop.name}» — ربات: {state}\n\n{_help(h)}", _admin_keyboard(shop)
    )


def _help(h: _Bot) -> str:
    channel = (
        ""
        if h.bot.platform == "bale"
        else "📢 کانال تلگرام دارید؟ من را ادمین کانال کنید تا هر پست محصول جدید خودکار ثبت شود.\n"
    )
    return ADMIN_HELP.format(channel=channel)


def _command(text: str) -> str:
    if not text.startswith("/"):
        return ""
    return text.split()[0].split("@")[0].lower()


# ---------------------------------------------------------------------------- the owner


async def _on_admin_message(
    h: _Bot,
    session: TelegramSession,
    admin: TelegramAdmin,
    message: dict[str, Any],
    chat_id: int,
    text: str,
) -> None:
    shop = await h.db.get(Shop, admin.shop_id)
    if shop is None:
        return
    command = _command(text)
    if command == "/cancel":
        session.state = {}
        await h.db.commit()
        await h.send(chat_id, "لغو شد.", _admin_keyboard(shop))
        return
    reply_to = (session.state or {}).get("reply_to")
    if reply_to and text and not command:
        await _relay_owner_reply(h, session, shop, chat_id, reply_to, text)
        return
    if text in (BUTTON_HELP, "/help"):
        await h.send(chat_id, _help(h), _admin_keyboard(shop))
        return
    if text in (BUTTON_PRODUCTS, "/products"):
        await h.send(chat_id, await _products_summary(h, shop), _admin_keyboard(shop))
        return
    if text in (BUTTON_WALLET, "/wallet"):
        await h.send(chat_id, _wallet_summary(shop), _admin_keyboard(shop))
        return
    if text in (BUTTON_PAUSE, BUTTON_RESUME, "/pause", "/resume"):
        shop.bot_enabled = text in (BUTTON_RESUME, "/resume")
        await h.db.commit()
        state = (
            "روشن شد ✅ و به مشتری‌ها جواب می‌دهد."
            if shop.bot_enabled
            else ("خاموش شد ⏸ و تا روشن کردن دوباره به مشتری‌ها جواب نمی‌دهد.")
        )
        await h.send(chat_id, f"ربات {state}", _admin_keyboard(shop))
        return
    if command:
        await h.send(chat_id, "این دستور را نمی‌شناسم. /help را ببینید.", _admin_keyboard(shop))
        return

    await h.typing(chat_id)
    try:
        proposal = await _proposal_from_admin_message(h, shop, session, message, chat_id, text)
    except teach.TeachError as exc:
        await h.send(chat_id, str(exc))
        return
    if proposal is None:
        await h.send(
            chat_id,
            "این پیام را متوجه نشدم. متن، صوت، فایل، عکس یا لینک بفرستید؛ /help را هم ببینید.",
        )
        return
    await _show_proposal(h, session, chat_id, proposal)


async def _proposal_from_admin_message(
    h: _Bot,
    shop: Shop,
    session: TelegramSession,
    message: dict[str, Any],
    chat_id: int,
    text: str,
) -> TeachProposal | None:
    llm = h.ctx.llm
    if not llm.configured:
        raise teach.TeachError("هوش مصنوعی روی سرور فعال نیست.")

    origin = message.get("forward_origin") or {}
    if origin.get("type") == "channel" or message.get("forward_from_chat"):
        post = await _store_forwarded_post(h, shop, message)
        if not post.text:
            raise teach.TeachError("این پست متنی ندارد؛ توضیح محصول را بنویسید.")
        return await teach.propose(
            h.db,
            llm,
            shop,
            post.text,
            source="telegram_post",
            label="پست فورواردشده",
            telegram_post_id=post.id,
        )

    voice = message.get("voice") or message.get("audio")
    if voice:
        if not llm.can_transcribe:
            raise teach.TeachError("فعلا پیام صوتی را نمی‌فهمم؛ لطفا متن را تایپ کنید.")
        if not billing.can_spend(shop):
            raise teach.TeachError("موجودی کیف پول تمام شده است؛ از پنل آن را شارژ کنید.")
        data = await _download(h, voice["file_id"])
        transcript = await llm.transcribe(data, voice.get("file_name") or "voice.ogg")
        duration = int(voice.get("duration") or 0)
        await billing.charge_amount(
            h.db,
            shop,
            billing.voice_cost(duration),
            "تبدیل پیام صوتی به متن",
            {"seconds": duration},
        )
        if not transcript:
            raise teach.TeachError("صدایی در این پیام تشخیص داده نشد.")
        await h.send(chat_id, f"🎙 شنیدم:\n«{transcript[:1500]}»")
        return await _propose_said(
            h, shop, session, chat_id, transcript, "voice", f"پیام صوتی {duration} ثانیه‌ای"
        )

    document = message.get("document")
    if document:
        filename = document.get("file_name") or "file"
        data = await _download(h, document["file_id"])
        content = await teach.text_from_file(filename, data, llm)
        if text:
            content = f"{text}\n\n{content}"
        return await teach.propose(h.db, llm, shop, content, source="file", label=filename)

    photos = message.get("photo")
    if photos:
        biggest = photos[-1]
        if text:
            # A product photo with its description: the product keeps this photo.
            post = TelegramPost(
                shop_id=shop.id,
                bot_id=h.bot.id,
                chat_id=chat_id,
                message_id=int(message["message_id"]),
                text=text,
                photo_file_id=biggest["file_id"],
                posted_at=utcnow(),
            )
            h.db.add(post)
            await h.db.commit()
            return await teach.propose(
                h.db,
                llm,
                shop,
                text,
                source="telegram_post",
                label="عکس محصول",
                telegram_post_id=post.id,
            )
        data = await _download(h, biggest["file_id"])
        read = await teach.text_from_file("photo.jpg", data, llm)
        return await teach.propose(h.db, llm, shop, read, source="photo", label="عکس")

    if not text:
        return None
    url = teach.URL_PATTERN.search(text)
    if url and len(text) - len(url.group(0)) < 40:
        return await teach.propose_from_url(h.db, h.ctx.http, llm, shop, url.group(0))
    return await _propose_said(h, shop, session, chat_id, text, "text", text[:100])


async def _propose_said(
    h: _Bot,
    shop: Shop,
    session: TelegramSession,
    chat_id: int,
    said: str,
    source: str,
    label: str,
) -> TeachProposal:
    """Something the owner said (typed or spoken), read in the light of the conversation.

    If a proposal still waits for their OK, this message completes or corrects it ("make the
    price 2.5 million"): it is read together with that proposal's input and replaces it.
    """
    _remember(session, "owner", said)
    await h.db.commit()
    text = said
    pending = await _pending_proposal(h, session)
    if pending is not None:
        earlier = str((pending.changes or {}).get("input") or "")
        text = (
            f"{earlier}\n\n[پیام بعدی صاحب فروشگاه که پیام بالا را کامل یا اصلاح می‌کند؛ "
            f"نتیجه‌ی نهایی هر دو را بده]\n{said}"
        )
        await _retire(h, session, chat_id, pending)
    return await teach.propose(
        h.db, h.ctx.llm, shop, text, source=source, label=label, context=_history_text(session)
    )


def _remember(session: TelegramSession, role: str, text: str) -> None:
    history = list((session.state or {}).get("history") or [])[-(HISTORY_TURNS - 1) :]
    history.append({"r": role, "t": text[:1500]})
    session.state = {**(session.state or {}), "history": history}


def _history_text(session: TelegramSession) -> str:
    # The newest turn is the message being read; the AI gets it as the input itself.
    turns = list((session.state or {}).get("history") or [])[:-1]
    return "\n".join(f"{'Owner' if t['r'] == 'owner' else 'You'}: {t['t']}" for t in turns)


async def _pending_proposal(h: _Bot, session: TelegramSession) -> TeachProposal | None:
    raw = (session.state or {}).get("proposal_id")
    if not raw:
        return None
    try:
        proposal = await h.db.get(TeachProposal, uuid.UUID(raw))
    except ValueError:
        return None
    if proposal is None or proposal.status != ProposalStatus.PENDING:
        return None
    if utcnow() - as_utc(proposal.created_at) > FOLLOW_UP_WINDOW:
        return None
    return proposal


async def _retire(h: _Bot, session: TelegramSession, chat_id: int, proposal: TeachProposal) -> None:
    """The owner refined this proposal: drop it and its buttons (a new one replaces it)."""
    await teach.discard(h.db, proposal)
    message_id = (session.state or {}).get("proposal_message_id")
    if message_id:
        try:
            await h.client.edit_reply_markup(h.token, chat_id, int(message_id), None)
        except TelegramError:
            pass
    session.state = {
        k: v
        for k, v in (session.state or {}).items()
        if k not in ("proposal_id", "proposal_message_id")
    }
    await h.db.commit()


async def _download(h: _Bot, file_id: str) -> bytes:
    try:
        return await h.client.download_file(h.token, file_id, MAX_DOWNLOAD_BYTES)
    except TelegramError as exc:
        if exc.status == 413:
            raise teach.TeachError("فایل بزرگ‌تر از ۲۰ مگابایت است.") from None
        raise teach.TeachError("دریافت فایل از تلگرام ممکن نشد؛ دوباره بفرستید.") from None


async def _store_forwarded_post(h: _Bot, shop: Shop, message: dict[str, Any]) -> TelegramPost:
    origin = message.get("forward_origin") or {}
    chat = origin.get("chat") or message.get("forward_from_chat") or {}
    chat_id = int(chat.get("id") or message["chat"]["id"])
    message_id = int(
        origin.get("message_id") or message.get("forward_from_message_id") or message["message_id"]
    )
    photos = message.get("photo") or []
    post = await h.db.scalar(
        select(TelegramPost).where(
            TelegramPost.chat_id == chat_id, TelegramPost.message_id == message_id
        )
    )
    if post is None:
        post = TelegramPost(
            shop_id=shop.id, bot_id=h.bot.id, chat_id=chat_id, message_id=message_id
        )
        h.db.add(post)
    post.shop_id = shop.id
    post.channel_username = chat.get("username")
    post.text = (message.get("text") or message.get("caption") or "").strip()
    post.photo_file_id = photos[-1]["file_id"] if photos else post.photo_file_id
    post.posted_at = _timestamp(origin.get("date"))
    await h.db.commit()
    return post


async def _show_proposal(
    h: _Bot, session: TelegramSession, chat_id: int, proposal: TeachProposal
) -> None:
    text = teach.describe(proposal)
    _remember(session, "bot", text)
    if teach.is_empty(proposal):
        await teach.discard(h.db, proposal)
        await h.db.commit()
        await h.send(chat_id, text)
        return
    keyboard = inline_keyboard(
        [[("✅ ثبت کن", f"apply:{proposal.id}"), ("❌ بی‌خیال", f"discard:{proposal.id}")]]
    )
    message_id = await h.send(chat_id, text, keyboard)
    session.state = {
        **session.state,
        "proposal_id": str(proposal.id),
        "proposal_message_id": message_id,
    }
    await h.db.commit()


async def _relay_owner_reply(
    h: _Bot, session: TelegramSession, shop: Shop, chat_id: int, conversation_id: str, text: str
) -> None:
    session.state = {k: v for k, v in (session.state or {}).items() if k != "reply_to"}
    await h.db.commit()
    conversation = await _conversation(h, shop, conversation_id)
    if conversation is None:
        await h.send(chat_id, "این گفتگو پیدا نشد.", _admin_keyboard(shop))
        return
    error = await send_owner_reply(h.db, shop, conversation, text, h.client, h.ctx.http)
    if error:
        await h.send(chat_id, error, _admin_keyboard(shop))
        return
    await h.send(
        chat_id, f"✅ برای {customer_label(conversation)} فرستاده شد.", _admin_keyboard(shop)
    )


async def send_owner_reply(
    db: AsyncSession,
    shop: Shop,
    conversation: Conversation,
    text: str,
    telegram: TelegramClient | None,
    http: httpx.AsyncClient,
) -> str | None:
    """Send the owner's own answer to a customer on the conversation's channel.

    Returns a Persian error, or None on success. Used by the bot relay and the panel.
    """
    sender = await sender_for(
        db, shop, conversation, Gateways(instagram=InstagramClient(http), telegram=telegram)
    )
    if sender is None:
        return "این کانال الان وصل نیست؛ از خود برنامه به مشتری جواب بدهید."
    last = conversation.last_customer_message_at
    if sender.reply_window and last and utcnow() - as_utc(last) > sender.reply_window:
        return "بیش از ۲۴ ساعت از پیام مشتری گذشته و این کانال اجازه‌ی جواب نمی‌دهد."
    external_id = None
    for chunk in split_text(text, sender.max_text_length):
        try:
            external_id = await sender.send_text(chunk)
        except SendError:
            return "فرستادن پیام ناموفق بود؛ کمی بعد دوباره امتحان کنید."
    await messaging.record_owner_message(db, shop, conversation, text=text, external_id=external_id)
    return None


async def _products_summary(h: _Bot, shop: Shop) -> str:
    rows = (await h.db.scalars(select(Product).where(Product.shop_id == shop.id))).all()
    if not rows:
        return (
            "هنوز محصولی ثبت نشده. محصولاتتان را برایم بنویسید، صوت یا فایل بفرستید، "
            "یا لینک گوگل شیت/داک را بفرستید."
        )
    out_of_stock = sum(1 for p in rows if p.stock == 0)
    names = list(dict.fromkeys(p.name for p in rows))
    lines = [
        f"📦 {len(rows)} محصول (با رنگ و سایز) از {len(names)} مدل؛ {out_of_stock} مورد ناموجود.",
        "",
        *[f"• {n}" for n in names[:25]],
    ]
    if len(names) > 25:
        lines.append(f"… و {len(names) - 25} مدل دیگر")
    lines.append(f"\nلیست کامل و جستجو در پنل: {get_settings().frontend_url}/products")
    return "\n".join(lines)


def _wallet_summary(shop: Shop) -> str:
    plan = billing.PLANS[shop.plan].label
    return (
        f"💰 موجودی کیف پول: {billing.toman(shop.balance_rial)}\nپلن: {plan}\n\n"
        f"برای شارژ به پنل بروید: {get_settings().frontend_url}/billing"
    )


# ---------------------------------------------------------------------------- buttons


async def _on_callback(h: _Bot, query: dict[str, Any]) -> None:
    user_id = int((query.get("from") or {}).get("id") or 0)
    data = str(query.get("data") or "")
    message = query.get("message") or {}
    chat_id = int((message.get("chat") or {}).get("id") or user_id)
    action, _, raw_id = data.partition(":")
    notice = ""
    admin = await _admin_for(h, user_id)
    if admin is None:
        notice = "اول حساب تلگرامتان را از پنل وصل کنید."
    else:
        shop = await h.db.get(Shop, admin.shop_id)
        if shop is not None:
            notice = await _run_callback(h, admin, shop, action, raw_id, chat_id)
            if message.get("message_id") and action in ("apply", "discard", "undo"):
                try:
                    await h.client.edit_reply_markup(
                        h.token, chat_id, int(message["message_id"]), None
                    )
                except TelegramError:
                    pass
    try:
        await h.client.answer_callback(h.token, str(query.get("id") or ""), notice)
    except TelegramError:
        pass


async def _run_callback(
    h: _Bot, admin: TelegramAdmin, shop: Shop, action: str, raw_id: str, chat_id: int
) -> str:
    if action in ("apply", "discard", "undo"):
        proposal = await _proposal(h, shop, raw_id)
        if proposal is None:
            return "این مورد پیدا نشد."
        session = await _session(h, admin.telegram_user_id)
        if action == "apply":
            try:
                result = await teach.apply(h.db, shop, proposal, h.ctx.http)
            except teach.TeachError as exc:
                return str(exc)
            _close_proposal(session, f"ثبت شد: {result}")
            await h.db.commit()
            await h.send(chat_id, f"✅ {result}")
            return "ثبت شد"
        if action == "discard":
            await teach.discard(h.db, proposal)
            _close_proposal(session, "صاحب فروشگاه گفت ثبت نشود.")
            await h.db.commit()
            await h.send(chat_id, "باشه، چیزی ثبت نشد.")
            return "ثبت نشد"
        removed = await teach.undo(h.db, shop, proposal)
        await h.send(chat_id, f"↩️ {removed} محصول برداشته شد.")
        return "برگردانده شد"

    conversation = await _conversation(h, shop, raw_id)
    if conversation is None:
        return "این گفتگو پیدا نشد."
    if action == "reply":
        session = await _session(h, admin.telegram_user_id)
        session.mode = "admin"
        session.state = {**(session.state or {}), "reply_to": str(conversation.id)}
        await h.db.commit()
        await h.send(
            chat_id,
            f"جوابتان به {customer_label(conversation)} را بنویسید؛ همین‌جا برایش فرستاده "
            "می‌شود. (/cancel برای لغو)",
        )
        return "منتظر پیام شما"
    if action == "resolve":
        if conversation.handoff_open:
            conversation.handoff_resolved_at = utcnow()
            conversation.handoff_resolved_by = HandoffResolution.MANUAL
            await h.db.commit()
        return "بسته شد"
    if action == "pause":
        conversation.bot_paused_until = utcnow() + timedelta(days=3650)
        await h.db.commit()
        return "ربات در این گفتگو ساکت شد"
    return ""


def _close_proposal(session: TelegramSession, outcome: str) -> None:
    _remember(session, "bot", outcome)
    session.state = {
        k: v for k, v in session.state.items() if k not in ("proposal_id", "proposal_message_id")
    }


async def _proposal(h: _Bot, shop: Shop, raw_id: str) -> TeachProposal | None:
    try:
        proposal = await h.db.get(TeachProposal, uuid.UUID(raw_id))
    except ValueError:
        return None
    return proposal if proposal and proposal.shop_id == shop.id else None


async def _conversation(h: _Bot, shop: Shop, raw_id: str) -> Conversation | None:
    try:
        conversation = await h.db.get(Conversation, uuid.UUID(raw_id))
    except ValueError:
        return None
    return conversation if conversation and conversation.shop_id == shop.id else None


# ---------------------------------------------------------------------------- customers


async def _on_customer_message(
    h: _Bot,
    session: TelegramSession,
    message: dict[str, Any],
    user: dict[str, Any],
    chat_id: int,
) -> None:
    shop_id = h.bot.shop_id or session.shop_id
    shop = await h.db.get(Shop, shop_id) if shop_id else None
    if shop is None:
        # Some apps drop the start link's parameter: the customer can send the shop code.
        code = (message.get("text") or "").strip().lower().removeprefix("s_")
        shop = await h.db.scalar(select(Shop).where(Shop.slug == code)) if code else None
        if shop is not None:
            session.shop_id = shop.id
            session.mode = "customer"
            await h.db.commit()
            await h.send(chat_id, _welcome(shop))
            return
        await h.send(
            chat_id,
            "برای گفتگو با یک فروشگاه، از لینکی که خود فروشگاه گذاشته وارد شوید یا کد "
            "فروشگاه را همین‌جا بفرستید. اگر صاحب فروشگاه هستید، حسابتان را از پنل «جواب» "
            "وصل کنید.",
        )
        return
    if not shop.channel_enabled(h.bot.platform):
        return
    conversation = await messaging.get_or_create_conversation(
        h.db, shop.id, h.channel, bot_ref(h.bot), str(chat_id)
    )
    _remember_customer(conversation, user)
    await messaging.record_customer_message(
        h.db,
        conversation,
        external_id=telegram_message_key(bot_ref(h.bot), chat_id, int(message["message_id"])),
        text=display_text(message),
        at=_timestamp(message.get("date")) or utcnow(),
        queue=h.ctx.queue,
        debounce_seconds=h.ctx.debounce_seconds,
    )


def _remember_customer(conversation: Conversation, user: dict[str, Any]) -> None:
    conversation.customer_username = (user.get("username") or "")[:64]
    name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
    conversation.customer_name = name[:128] or None


_MEDIA_MARKERS = (
    ("photo", "[photo]"),
    ("video", "[video]"),
    ("voice", "[voice]"),
    ("audio", "[audio]"),
    ("document", "[file]"),
    ("sticker", "[sticker]"),
    ("animation", "[gif]"),
    ("video_note", "[video]"),
    ("location", "[location]"),
    ("contact", "[contact]"),
)


def display_text(message: dict[str, Any]) -> str:
    """Text as stored in history; non-text content becomes a marker like `[photo]`."""
    text = (message.get("text") or message.get("caption") or "").strip()
    markers = [marker for key, marker in _MEDIA_MARKERS if message.get(key)]
    if message.get("sticker") and message["sticker"].get("emoji"):
        markers = [f"[sticker {message['sticker']['emoji']}]"]
    return " ".join(p for p in (text, " ".join(markers)) if p) or "[message]"


# ---------------------------------------------------------------------------- channels


async def _on_membership(h: _Bot, update: dict[str, Any]) -> None:
    chat = update.get("chat") or {}
    if chat.get("type") != "channel":
        return
    status = (update.get("new_chat_member") or {}).get("status")
    chat_id = int(chat["id"])
    channel = await h.db.scalar(
        select(TelegramChannel).where(
            TelegramChannel.bot_id == h.bot.id, TelegramChannel.chat_id == chat_id
        )
    )
    if status not in ("administrator", "creator"):
        if channel is not None and channel.is_active:
            channel.is_active = False
            await h.db.commit()
        return
    admin = await _admin_for(h, int((update.get("from") or {}).get("id") or 0))
    if admin is None:
        return  # we can't tell which shop this channel belongs to
    if channel is None:
        channel = TelegramChannel(shop_id=admin.shop_id, bot_id=h.bot.id, chat_id=chat_id)
        h.db.add(channel)
    channel.shop_id = admin.shop_id
    channel.title = (chat.get("title") or "")[:255]
    channel.username = chat.get("username")
    channel.is_active = True
    await h.db.commit()
    await h.send(
        admin.telegram_user_id,
        f"✅ کانال «{channel.title}» وصل شد. از این به بعد هر پست محصول جدید در کانال، "
        "خودکار به لیست محصولات اضافه می‌شود و خبرتان می‌کنم.\n\n"
        "برای پست‌های قبلی، آن‌ها را برای من فوروارد کنید.",
    )


async def _on_channel_post(h: _Bot, post_message: dict[str, Any], *, edited: bool) -> None:
    chat = post_message.get("chat") or {}
    channel = await h.db.scalar(
        select(TelegramChannel).where(
            TelegramChannel.bot_id == h.bot.id,
            TelegramChannel.chat_id == int(chat.get("id") or 0),
            TelegramChannel.is_active.is_(True),
        )
    )
    if channel is None:
        return
    shop = await h.db.get(Shop, channel.shop_id)
    if shop is None:
        return
    message_id = int(post_message["message_id"])
    text = (post_message.get("text") or post_message.get("caption") or "").strip()
    photos = post_message.get("photo") or []
    group = post_message.get("media_group_id")

    post = await h.db.scalar(
        select(TelegramPost).where(
            TelegramPost.chat_id == channel.chat_id, TelegramPost.message_id == message_id
        )
    )
    if post is None:
        post = TelegramPost(
            shop_id=shop.id, bot_id=h.bot.id, chat_id=channel.chat_id, message_id=message_id
        )
        h.db.add(post)
    post.channel_username = chat.get("username")
    post.text = text
    post.media_group_id = group
    if photos:
        post.photo_file_id = photos[-1]["file_id"]
    post.posted_at = _timestamp(post_message.get("date"))
    await h.db.commit()

    if not text:
        return  # an album photo without the caption; the captioned item carries the product
    if group and not post.photo_file_id:
        sibling = await h.db.scalar(
            select(TelegramPost).where(
                TelegramPost.media_group_id == group, TelegramPost.photo_file_id.is_not(None)
            )
        )
        if sibling is not None:
            post.photo_file_id = sibling.photo_file_id
            await h.db.commit()
    if not h.ctx.llm.configured or not billing.can_spend(shop):
        return
    if edited:
        # Re-read the post: its products are replaced by what the edited text says.
        await h.db.execute(
            delete(Product).where(
                Product.telegram_post_id == post.id,
                Product.origin == ProductOrigin.TELEGRAM_POST,
            )
        )
        await h.db.commit()
    try:
        proposal = await teach.propose(
            h.db,
            h.ctx.llm,
            shop,
            text,
            source="telegram_post",
            label=f"پست کانال {channel.title}",
            telegram_post_id=post.id,
        )
    except teach.TeachError as exc:
        logger.info("channel post not read for shop %s: %s", shop.id, exc)
        return
    has_products = any(c["action"] == "create" for c in proposal.changes.get("products", []))
    if not has_products:
        await teach.discard(h.db, proposal)
        return
    # The owner published it themselves, so add it right away and offer an undo.
    # A post describes products; shop policies are taught deliberately, not from posts.
    knowledge_items = set(range(len(proposal.changes.get("knowledge") or [])))
    result = await teach.apply(h.db, shop, proposal, h.ctx.http, skip_knowledge=knowledge_items)
    verb = "ویرایش شد و دوباره خوانده شد" if edited else "خوانده شد"
    await h.ctx.notifier.message(
        shop,
        f"📢 پست کانال «{channel.title}» {verb}:\n{teach.describe(proposal)}\n\n{result}",
        inline_keyboard([[("↩️ برگردان", f"undo:{proposal.id}")]]),
    )


# ---------------------------------------------------------------------------- business


async def _on_business_connection(h: _Bot, data: dict[str, Any]) -> None:
    connection_id = str(data.get("id") or "")
    user = data.get("user") or {}
    if not connection_id or not user.get("id"):
        return
    user_id = int(user["id"])
    user_chat_id = int(data.get("user_chat_id") or user_id)
    rights = data.get("rights")
    can_reply = (
        bool(rights.get("can_reply"))
        if isinstance(rights, dict)
        else bool(data.get("can_reply", True))
    )
    enabled = bool(data.get("is_enabled", True))

    connection = await h.db.scalar(
        select(TelegramBusinessConnection).where(
            TelegramBusinessConnection.connection_id == connection_id
        )
    )
    admin = await _admin_for(h, user_id)
    if admin is None:
        if enabled:
            await h.send(
                user_chat_id,
                "برای اینکه «جواب» از طرف اکانت شما جواب بدهد، اول از پنل «جواب» (بخش تلگرام) "
                "حساب تلگرامتان را به فروشگاه وصل کنید و بعد دوباره ربات را در تنظیمات "
                "Telegram Business اضافه کنید.",
            )
        return
    if connection is None:
        connection = TelegramBusinessConnection(
            connection_id=connection_id,
            shop_id=admin.shop_id,
            bot_id=h.bot.id,
            telegram_user_id=user_id,
            user_chat_id=user_chat_id,
        )
        h.db.add(connection)
    connection.shop_id = admin.shop_id
    connection.bot_id = h.bot.id
    connection.can_reply = can_reply
    connection.is_enabled = enabled
    await h.db.commit()
    if not enabled:
        await h.send(user_chat_id, "اتصال «جواب» به اکانت تلگرام شما قطع شد.")
        return
    shop = await h.db.get(Shop, admin.shop_id)
    if shop is None:
        return
    notes = []
    if shop.plan not in PLANS_FOR_BUSINESS:
        notes.append(
            "⚠️ این امکان در پلن «بیزینس» است. تا پلن را از پنل ارتقا ندهید، پیام‌ها فقط در "
            "پنل ثبت می‌شوند و ربات جواب نمی‌دهد."
        )
    if not can_reply:
        notes.append("⚠️ در تنظیمات Telegram Business اجازه‌ی «پاسخ به پیام‌ها» را به ربات بدهید.")
    await h.send(
        user_chat_id,
        "✅ «جواب» به اکانت تلگرام شما وصل شد و از این به بعد به پیام‌های مشتری‌ها در "
        "چت‌های خصوصی‌تان جواب می‌دهد. هر وقت خودتان در یک گفتگو جواب بدهید، ربات در آن "
        "گفتگو کنار می‌کشد." + ("\n\n" + "\n".join(notes) if notes else ""),
    )


async def _on_business_message(h: _Bot, message: dict[str, Any]) -> None:
    connection_id = str(message.get("business_connection_id") or "")
    connection = await h.db.scalar(
        select(TelegramBusinessConnection).where(
            TelegramBusinessConnection.connection_id == connection_id,
            TelegramBusinessConnection.is_enabled.is_(True),
        )
    )
    if connection is None:
        return
    shop = await h.db.get(Shop, connection.shop_id)
    chat = message.get("chat") or {}
    if shop is None or chat.get("type") != "private":
        return
    chat_id = int(chat["id"])
    ref = business_ref(connection)
    external_id = telegram_message_key(ref, chat_id, int(message["message_id"]))
    if await messaging.message_exists(h.db, external_id) or message.get("sender_business_bot"):
        return  # our own answer
    conversation = await messaging.get_or_create_conversation(
        h.db, shop.id, Channel.TELEGRAM, ref, str(chat_id)
    )
    sender = message.get("from") or {}
    if int(sender.get("id") or 0) == connection.telegram_user_id:
        await messaging.record_owner_message(
            h.db, shop, conversation, text=display_text(message), external_id=external_id
        )
        return
    _remember_customer(conversation, chat)
    await messaging.record_customer_message(
        h.db,
        conversation,
        external_id=external_id,
        text=display_text(message),
        at=_timestamp(message.get("date")) or utcnow(),
        queue=h.ctx.queue,
        debounce_seconds=h.ctx.debounce_seconds,
    )


# ---------------------------------------------------------------------------- helpers


async def _session(h: _Bot, user_id: int) -> TelegramSession:
    session = await h.db.scalar(
        select(TelegramSession).where(
            TelegramSession.bot_id == h.bot.id, TelegramSession.telegram_user_id == user_id
        )
    )
    if session is None:
        session = TelegramSession(bot_id=h.bot.id, telegram_user_id=user_id, state={})
        h.db.add(session)
        await h.db.commit()
    return session


async def _admin_for(h: _Bot, user_id: int) -> TelegramAdmin | None:
    """The linked owner account, if this user is one (on a custom bot: of that bot's shop)."""
    if not user_id:
        return None
    admin = await h.db.scalar(
        select(TelegramAdmin).where(
            TelegramAdmin.platform == h.bot.platform, TelegramAdmin.telegram_user_id == user_id
        )
    )
    if admin is None:
        return None
    if h.bot.shop_id is not None and admin.shop_id != h.bot.shop_id:
        return None
    return admin


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, UTC)
    return None
