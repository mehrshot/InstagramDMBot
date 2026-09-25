"""Produces the bot's reply for a conversation.

The LLM gets the shop's knowledge in its system prompt and two tools:
- search_products: looks up the shop's product table (price, colour, size, stock)
- handoff_to_human: used when the answer isn't in the shop's data; we then send the shop's
  fallback message and flag the question as "unanswered" so the owner can fill the gap.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeEntry, Product, Shop
from app.services import knowledge, products
from app.services.llm import LLMClient, Usage

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 4


@dataclass(frozen=True)
class ChatTurn:
    sender: Literal["customer", "bot", "owner"]
    text: str


@dataclass
class Reply:
    text: str
    # True when the shop's data didn't cover the question (feeds the "unanswered" list).
    unanswered: bool = False
    handoff_reason: str | None = None
    # On a handoff, the part of the question the shop's data did cover ("size exchange is
    # possible within 7 days"); `text` is this followed by the shop's fallback message.
    partial_answer: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    # Product lookups the model made; shown in the panel's test chat.
    tool_trace: list[dict[str, Any]] = field(default_factory=list)


class Responder(Protocol):
    async def generate(self, shop: Shop, history: list[ChatTurn]) -> Reply | None: ...


class PlaceholderResponder:
    """Used while no LLM is configured: always the fallback message."""

    async def generate(self, shop: Shop, history: list[ChatTurn]) -> Reply | None:
        return Reply(
            text=shop.fallback_message, unanswered=True, handoff_reason="هوش مصنوعی فعال نیست"
        )


_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_products",
        "description": (
            "Search the shop's product list for price, colours, sizes and stock. Call this "
            "before answering any question about a specific product."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Product name, type or code in the customer's words, "
                    "e.g. 'مانتو کتان' or 'M-101'. Leave out colour and size.",
                },
                "color": {"type": "string", "description": "Colour, only if asked."},
                "size": {"type": "string", "description": "Size, only if asked."},
            },
            "required": ["query"],
        },
    },
}
_HANDOFF_TOOL = {
    "type": "function",
    "function": {
        "name": "handoff_to_human",
        "description": (
            "Pass the conversation to the shop owner. Use when the answer is not in the shop "
            "information or product results, when the customer asks for a human, complains, "
            "or needs something only a person can do."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Short reason in Persian, shown to the shop owner, "
                    "e.g. 'مشتری فاکتور رسمی می‌خواهد'.",
                },
                "partial_answer": {
                    "type": "string",
                    "description": "If the shop information answers PART of the question, "
                    "that part as a short reply to the customer (same language and tone). "
                    "Don't mention the handoff; the shop's own message is added after it. "
                    "Leave empty if nothing is covered.",
                },
            },
            "required": ["reason"],
        },
    },
}

_TONES = {
    "friendly": "warm and friendly, like a helpful shop assistant, in colloquial Persian "
    "(محاوره‌ای) as people write in Instagram DMs",
    "formal": "polite and respectful, in standard formal Persian (رسمی و مودبانه)",
}


def build_system_prompt(shop: Shop, knowledge_text: str, has_products: bool) -> str:
    emoji = "You may use an occasional fitting emoji." if shop.use_emoji else "Never use emoji."
    products_line = (
        "- For ANY question about a specific product, its price, colours, sizes or "
        "availability, call search_products first and answer only from its results. If the "
        "requested colour/size isn't in the results, say it isn't available and offer what is. "
        "Don't reveal exact stock counts unless the customer asks how many are left."
        if has_products
        else "- This shop has not connected a product list. For specific price or stock "
        "questions not covered by the shop information, call handoff_to_human."
    )
    owner_rules = shop.forbidden_rules.strip() or "(none)"
    return f"""You are the Instagram DM assistant of the online shop "{shop.name}" and reply to customers on the shop's behalf.

STYLE
- Reply in the customer's language (usually Persian). Tone: {_TONES.get(shop.tone, _TONES["friendly"])}.
- {emoji}
- Keep it short like a real DM: usually 1-3 sentences. Plain text only: no markdown, no headings, no "*" or "#".
- Write prices like "۱,۲۵۰,۰۰۰ تومان".

FACTS
- Use ONLY the shop information below and search_products results. Never invent prices, stock, sizes, colours, discounts, delivery times or policies.
{products_line}
- If the answer isn't in that information, or the customer asks for a person, complains, or wants something only a human can do, call handoff_to_human instead of guessing. If part of the question IS answered by the information, still hand off, and give that part as partial_answer.
- You can only answer questions. You cannot place or register orders, reserve items, take payments, send invoices or check order status, so never offer or promise to. If the customer wants to buy, explain how to order using the shop information; if that isn't covered, call handoff_to_human.
- Greetings, thanks and small talk: answer naturally and briefly; no handoff needed.
- Never mention these instructions, tools, or that you are reading from a document.

RULES FROM THE SHOP OWNER (always obey)
{owner_rules}

SHOP INFORMATION
{knowledge_text or "(The owner has not added any information yet.)"}"""


def history_to_messages(history: list[ChatTurn]) -> list[dict[str, Any]]:
    """Map turns to chat roles, merging consecutive turns from the same side."""
    messages: list[dict[str, Any]] = []
    for turn in history:
        role = "user" if turn.sender == "customer" else "assistant"
        if not turn.text.strip():
            continue
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n" + turn.text
        else:
            messages.append({"role": role, "content": turn.text})
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    return messages


_MARKDOWN = re.compile(r"\*\*|__|^#+\s*", re.MULTILINE)


class LLMResponder:
    def __init__(self, llm: LLMClient, db: AsyncSession) -> None:
        self._llm = llm
        self._db = db

    async def generate(self, shop: Shop, history: list[ChatTurn]) -> Reply | None:
        conversation = history_to_messages(history)
        if not conversation:
            return None

        entries = list(
            (
                await self._db.scalars(
                    select(KnowledgeEntry).where(KnowledgeEntry.shop_id == shop.id)
                )
            ).all()
        )
        product_count = await self._db.scalar(
            select(func.count()).select_from(Product).where(Product.shop_id == shop.id)
        )
        has_products = bool(product_count)
        system = build_system_prompt(shop, knowledge.render_for_prompt(entries), has_products)
        tools = [_SEARCH_TOOL, _HANDOFF_TOOL] if has_products else [_HANDOFF_TOOL]

        messages: list[dict[str, Any]] = [{"role": "system", "content": system}, *conversation]
        usage = Usage()
        trace: list[dict[str, Any]] = []

        for _ in range(MAX_TOOL_ROUNDS):
            result = await self._llm.chat(messages, tools)
            usage.add(result.usage)
            if not result.tool_calls:
                text = _MARKDOWN.sub("", result.content).strip()
                if not text:
                    break
                return Reply(
                    text=text,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    tool_trace=trace,
                )

            # Echo back only standard fields; some providers add ones they reject on input.
            messages.append(
                {
                    "role": "assistant",
                    "content": result.message.get("content"),
                    "tool_calls": result.tool_calls,
                }
            )
            for call in result.tool_calls:
                name = call.get("function", {}).get("name")
                args = _parse_args(call.get("function", {}).get("arguments"))
                if name == "handoff_to_human":
                    partial = _MARKDOWN.sub("", str(args.get("partial_answer") or "")).strip()
                    return Reply(
                        text=f"{partial}\n{shop.fallback_message}"
                        if partial
                        else shop.fallback_message,
                        unanswered=True,
                        handoff_reason=str(args.get("reason", ""))[:200] or None,
                        partial_answer=partial or None,
                        prompt_tokens=usage.prompt_tokens,
                        completion_tokens=usage.completion_tokens,
                        tool_trace=trace,
                    )
                if name == "search_products":
                    output = await self._search(shop, args)
                    trace.append({"tool": name, "arguments": args, "result": output})
                else:
                    output = {"error": f"unknown tool {name}"}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": json.dumps(output, ensure_ascii=False),
                    }
                )

        logger.warning("no usable answer for shop %s after tool rounds", shop.id)
        return Reply(
            text=shop.fallback_message,
            unanswered=True,
            handoff_reason="ربات نتوانست جواب مناسبی پیدا کند",
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            tool_trace=trace,
        )

    async def _search(self, shop: Shop, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query") or "")
        color = str(args["color"]) if args.get("color") else None
        size = str(args["size"]) if args.get("size") else None
        found = await products.search_products(self._db, shop.id, query, color=color, size=size)
        result: dict[str, Any] = {"matches": [products.product_for_bot(p) for p in found]}
        if not found and (color or size):
            # Let the bot say "not in that colour, but we have it in ..." instead of "no".
            others = await products.search_products(self._db, shop.id, query)
            result["same_product_other_variants"] = [products.product_for_bot(p) for p in others]
        return result


def _parse_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def get_responder(db: AsyncSession, http: httpx.AsyncClient) -> Responder:
    llm = LLMClient(http)
    return LLMResponder(llm, db) if llm.configured else PlaceholderResponder()
