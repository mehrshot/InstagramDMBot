"""Check an AI provider and the bot's behaviour on real customer situations.

  uv run python -m scripts.check_llm
  uv run python -m scripts.check_llm --model another-model-name --price-in 0.10 --price-out 0.50

Uses LLM_BASE_URL / LLM_API_KEY / LLM_MODEL from backend/.env and a throwaway in-memory copy of
the demo shop (same data as `scripts.seed_demo`), so nothing touches your real data. Run it
after every prompt or model change: each scenario is a case that once went wrong.
"""

import argparse
import asyncio
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base, InstagramPost, KnowledgeEntry, Product, Shop
from app.services.llm import LLMClient, LLMError
from app.services.responder import ChatTurn, LLMResponder, Reply
from scripts.seed_demo import KNOWLEDGE, POSTS, PRODUCTS

FALLBACK = "سوالتون رو ثبت کردم، همکارم به زودی جواب میده 🙏"
_FALSE_PROMISES = ("ثبت می‌کنم", "ثبت میکنم", "برات ثبت", "براتون ثبت", "ثبت کردم", "رزرو کردم")


def _has(*words: str) -> Callable[[str], bool]:
    return lambda text: any(w in text for w in words)


def _mostly_latin(text: str) -> bool:
    latin = len(re.findall(r"[A-Za-z]", text))
    persian = len(re.findall(r"[؀-ۿ]", text))
    return latin > persian


@dataclass
class Scenario:
    ask: str
    expect: str  # what a good answer does, shown when it fails
    handoff: bool | None  # must hand off (True), must not (False), either (None)
    check: Callable[[str], bool] = lambda text: True
    posts: bool | None = None  # must share Instagram posts (True), must not (False), either


SCENARIOS = [
    # Products
    Scenario(
        "سلام، مانتو کتان مشکی سایز ۴۴ دارید؟ قیمتش چنده؟",
        "price 1,250,000",
        False,
        _has("۱,۲۵۰,۰۰۰", "1,250,000", "۱٬۲۵۰٬۰۰۰"),
    ),
    Scenario("مانتو سرمه ای 44 دارید؟", "sold out, offers black", False, _has("مشکی")),
    Scenario("محصولات فروشگاهتون چیه؟", "names the products", False, _has("شومیز")),
    Scenario(
        "ارزون ترین چیزی که میتونم ازتون بخرم چیه؟", "shirt, 890,000", False, _has("۸۹۰", "890")
    ),
    # Sharing posts: when it helps, and only then
    Scenario(
        "میخوام برای دوستم کادو بخرم، ۲۰ سالشه. پیشنهادی دارید؟",
        "recommends products and shares their posts",
        False,
        posts=True,
    ),
    Scenario("قیمت این چنده؟ [story_reply]", "doesn't re-send the story's post", None, posts=False),
    # Shop information and handoffs
    Scenario("ارسال به شیراز چقدر طول میکشه؟", "3-5 working days", False, _has("۳", "3"), False),
    Scenario(
        "امکان مرجوعی دارید؟",
        "size exchange within 7 days + hands off refunds",
        True,
        _has("۷", "7"),
        False,
    ),
    Scenario("برای شرکتمون فاکتور رسمی با کد اقتصادی صادر می‌کنید؟", "hands off", True, posts=False),
    Scenario(
        "من مشتریتونم، یه تخفیف ریز نمیدید؟",
        "no invented discount, natural handoff",
        True,
        lambda t: t != FALLBACK and not _has("٪", "درصد")(t),
        False,
    ),
    Scenario("Hey there. do you ship to ontario?", "replies in English", True, _mostly_latin),
    # Conversation
    Scenario("هوا چطوره امروز", "brief friendly reply, no handoff", False, posts=False),
    Scenario(
        "سرویس هوش مصنوعی رو از کجا گرفتید؟",
        "honest, no provider names",
        False,
        lambda t: not _has("OpenAI", "GPT", "avalai", "AvalAI", "Gemini", "luna")(t),
        False,
    ),
    Scenario(
        "همون مانتو مشکی ۴۴ رو می‌خوام، برام ثبتش کن",
        "no fake order",
        None,
        lambda t: not _has(*_FALSE_PROMISES)(t),
    ),
]


async def _demo_shop(sessions: async_sessionmaker) -> Shop:
    async with sessions() as db:
        shop = Shop(owner_id=uuid.uuid4(), name="مزون مهسا", fallback_message=FALLBACK)
        db.add(shop)
        await db.flush()
        db.add_all(
            KnowledgeEntry(shop_id=shop.id, section=s, title=t, content=c) for s, t, c in KNOWLEDGE
        )
        db.add_all(
            Product(
                shop_id=shop.id,
                sku=sku,
                name=name,
                category=cat,
                color=color,
                size=size,
                price=price,
                stock=stock,
                extra={},
            )
            for sku, name, cat, color, size, price, stock in PRODUCTS
        )
        db.add_all(
            InstagramPost(
                shop_id=shop.id,
                ig_media_id=media_id,
                permalink=f"https://www.instagram.com/p/{code}/",
                caption=caption,
            )
            for media_id, code, caption, _days in POSTS
        )
        await db.commit()
        return shop


def _judge(s: Scenario, reply: Reply) -> str | None:
    """None when the reply is good, otherwise what went wrong."""
    if s.posts is True and not reply.posts:
        return "should have shared the product posts"
    if s.posts is False and reply.posts:
        return "shared posts where they don't help"
    if s.handoff is True and not reply.unanswered:
        return "should have handed off to the owner"
    if s.handoff is False and reply.unanswered:
        return "handed off although it could answer"
    if not s.check(reply.text):
        return f"expected: {s.expect}"
    return None


async def main(model: str | None, price_in: float | None, price_out: float | None) -> None:
    settings = get_settings()
    if model:
        settings.llm_model = model
    if not settings.llm_configured:
        raise SystemExit("Set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in backend/.env first.")
    print(f"provider: {settings.llm_base_url}\nmodel:    {settings.llm_model}\n")

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    shop = await _demo_shop(sessions)

    passed = 0
    total_in = total_out = 0
    async with httpx.AsyncClient() as http:
        for s in SCENARIOS:
            async with sessions() as db:
                responder = LLMResponder(LLMClient(http, settings), db)
                started = time.perf_counter()
                try:
                    reply = await responder.generate(shop, [ChatTurn("customer", s.ask)])
                except LLMError as exc:
                    print(f"✗ {s.ask}\n  ERROR: {exc}\n")
                    continue
                seconds = time.perf_counter() - started
            problem = _judge(s, reply)
            passed += problem is None
            total_in += reply.prompt_tokens or 0
            total_out += reply.completion_tokens or 0
            flag = " [handed off]" if reply.unanswered else ""
            if reply.posts:
                codes = [post.permalink.rstrip("/").rsplit("/", 1)[-1] for post in reply.posts]
                flag += " + posts: " + ", ".join(codes)
            print(f"{'✓' if problem is None else '✗'} {s.ask}")
            print(f"  → {reply.text}{flag}")
            if problem:
                print(f"  !! {problem}")
            tokens = f"{reply.prompt_tokens}/{reply.completion_tokens}"
            print(f"  {seconds:.1f}s · tokens in/out {tokens}\n")
    await engine.dispose()

    print(f"{passed}/{len(SCENARIOS)} scenarios passed")
    if price_in is not None and price_out is not None:
        per_reply = (total_in * price_in + total_out * price_out) / 1_000_000 / len(SCENARIOS)
        print(f"≈ ${per_reply:.5f} per reply → ${per_reply * 1000:.2f} per 1,000 replies")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", help="override LLM_MODEL for this run")
    parser.add_argument("--price-in", type=float, help="USD per 1M input tokens (cost estimate)")
    parser.add_argument("--price-out", type=float, help="USD per 1M output tokens")
    args = parser.parse_args()
    asyncio.run(main(args.model, args.price_in, args.price_out))
