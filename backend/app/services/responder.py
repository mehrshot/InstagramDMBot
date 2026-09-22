"""Produces the bot's reply for a conversation.

Day 2 ships a placeholder that always answers with the shop's fallback message so the
Instagram pipeline can be tested end to end. Day 3 replaces it with the LLM responder.
"""

from dataclasses import dataclass
from typing import Protocol

from app.models import Message, Shop


@dataclass(frozen=True)
class Reply:
    text: str
    # True when the shop's data didn't cover the question (feeds the "unanswered" list).
    unanswered: bool = False
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class Responder(Protocol):
    async def generate(self, shop: Shop, history: list[Message]) -> Reply | None: ...


class PlaceholderResponder:
    async def generate(self, shop: Shop, history: list[Message]) -> Reply | None:
        return Reply(text=shop.fallback_message, unanswered=True)


def get_responder() -> Responder:
    return PlaceholderResponder()
