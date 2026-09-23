"""Background worker (arq). Run with: arq app.worker.WorkerSettings

The webhook endpoint only verifies and enqueues, so it can answer Meta immediately;
all database and network work happens here.
"""

import logging
import uuid
from datetime import datetime
from typing import Any

import httpx
from arq import Retry, cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.queue import ArqQueue
from app.services import instagram_accounts, messaging, products
from app.services.instagram import InstagramClient, InstagramError
from app.services.llm import LLMError
from app.services.responder import get_responder
from app.services.webhook import MessagingEvent

logger = logging.getLogger(__name__)


async def process_event(ctx: dict[str, Any], event: MessagingEvent) -> None:
    async with SessionLocal() as db:
        await messaging.handle_event(
            db,
            event,
            ctx["queue"],
            debounce_seconds=get_settings().reply_debounce_seconds,
            instagram=InstagramClient(ctx["http"]),
        )


async def reply_conversation(ctx: dict[str, Any], conversation_id: str, trigger_at: str) -> None:
    async with SessionLocal() as db:
        try:
            await messaging.reply_to_conversation(
                db,
                uuid.UUID(conversation_id),
                datetime.fromisoformat(trigger_at),
                InstagramClient(ctx["http"]),
                get_responder(db, ctx["http"]),
            )
        except (InstagramError, LLMError) as exc:
            # Only retryable errors propagate out of reply_to_conversation.
            logger.warning("reply failed (try %s), retrying: %s", ctx.get("job_try"), exc)
            raise Retry(defer=ctx.get("job_try", 1) * 10) from exc


async def sync_product_sheets(ctx: dict[str, Any]) -> None:
    async with SessionLocal() as db:
        await products.sync_due_sources(db, ctx["http"])


async def refresh_instagram_tokens(ctx: dict[str, Any]) -> None:
    async with SessionLocal() as db:
        count = await instagram_accounts.refresh_expiring_tokens(db, InstagramClient(ctx["http"]))
    logger.info("refreshed %d instagram tokens", count)


async def startup(ctx: dict[str, Any]) -> None:
    ctx["http"] = httpx.AsyncClient(timeout=20)
    ctx["queue"] = ArqQueue(ctx["redis"])


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["http"].aclose()


# Used by InlineQueue for local development without Redis.
FUNCTIONS = {
    "process_event": process_event,
    "reply_conversation": reply_conversation,
}


class WorkerSettings:
    functions = [process_event, reply_conversation]
    cron_jobs = [
        cron(refresh_instagram_tokens, hour={3}, minute={0}),
        cron(sync_product_sheets, minute=set(range(0, 60, 5))),
    ]
    on_startup = startup
    on_shutdown = shutdown
    max_tries = 5
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
