"""Check an AI provider before using it for real: connection, Persian quality, tool use, cost.

  uv run python -m scripts.check_llm
  uv run python -m scripts.check_llm --model another-model-name

Uses LLM_BASE_URL / LLM_API_KEY / LLM_MODEL from backend/.env and a throwaway in-memory shop,
so nothing touches your real data. Each scenario is what a real customer would send.
"""

import argparse
import asyncio
import time
import uuid

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base, KnowledgeEntry, KnowledgeSection, Product, Shop
from app.services.llm import LLMClient, LLMError
from app.services.responder import ChatTurn, LLMResponder

SCENARIOS = [
    # (what the customer writes, what a good answer must do)
    ("سلام، مانتو کتان مشکی سایز ۴۴ دارید؟ قیمتش چنده؟", "product"),
    ("ارسال به شیراز چقدر طول میکشه؟", "knowledge"),
    ("برای شرکتمون فاکتور رسمی با کد اقتصادی صادر می‌کنید؟", "handoff"),
]


async def _demo_shop(sessions: async_sessionmaker) -> Shop:
    async with sessions() as db:
        shop = Shop(
            owner_id=uuid.uuid4(), name="مزون تست جواب", fallback_message="همکارم جواب میده"
        )
        db.add(shop)
        await db.flush()
        db.add_all(
            [
                KnowledgeEntry(
                    shop_id=shop.id,
                    section=KnowledgeSection.SHIPPING,
                    content="ارسال با پست پیشتاز ۳ تا ۵ روز کاری، هزینه ۸۵ هزار تومان.",
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
                Product(
                    shop_id=shop.id,
                    name="مانتو کتان",
                    color="مشکی",
                    size="46",
                    price=1250000,
                    stock=0,
                    extra={},
                ),
            ]
        )
        await db.commit()
        return shop


def _verdict(kind: str, reply) -> tuple[bool, str]:
    if kind == "product":
        ok = bool(reply.tool_trace) and not reply.unanswered
        return ok, "searched the product list" if reply.tool_trace else "did NOT search products"
    if kind == "knowledge":
        ok = not reply.unanswered and (
            "پیشتاز" in reply.text or "۳" in reply.text or "3" in reply.text
        )
        return ok, "answered from shop info" if ok else "did not use shop info"
    ok = reply.unanswered
    return (
        ok,
        "handed off to the owner" if ok else "answered instead of handing off (may invent facts)",
    )


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
        for text, kind in SCENARIOS:
            async with sessions() as db:
                responder = LLMResponder(LLMClient(http, settings), db)
                started = time.perf_counter()
                try:
                    reply = await responder.generate(shop, [ChatTurn("customer", text)])
                except LLMError as exc:
                    print(f"✗ {text}\n  ERROR: {exc}\n")
                    continue
                seconds = time.perf_counter() - started
            ok, why = _verdict(kind, reply)
            passed += ok
            total_in += reply.prompt_tokens or 0
            total_out += reply.completion_tokens or 0
            print(f"{'✓' if ok else '✗'} {text}")
            print(f"  → {reply.text}")
            tokens = f"{reply.prompt_tokens}/{reply.completion_tokens}"
            print(f"  {why} · {seconds:.1f}s · tokens in/out {tokens}\n")
    await engine.dispose()

    print(f"{passed}/{len(SCENARIOS)} scenarios passed")
    if price_in is not None and price_out is not None and passed:
        per_reply = (total_in * price_in + total_out * price_out) / 1_000_000 / len(SCENARIOS)
        print(f"≈ ${per_reply:.5f} per reply → ${per_reply * 1000:.2f} per 1,000 replies")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", help="override LLM_MODEL for this run")
    parser.add_argument(
        "--price-in", type=float, help="USD per 1M input tokens (for a cost estimate)"
    )
    parser.add_argument("--price-out", type=float, help="USD per 1M output tokens")
    args = parser.parse_args()
    asyncio.run(main(args.model, args.price_in, args.price_out))
