"""Background worker (arq).

Webhook handlers enqueue jobs here so they can return 200 to Meta immediately.
Day 2+ adds: process_incoming_message, sync_product_sheet, refresh_instagram_tokens.
"""

from typing import Any

from arq.connections import RedisSettings

from app.core.config import get_settings


async def heartbeat(ctx: dict[str, Any]) -> str:
    return "ok"


class WorkerSettings:
    functions = [heartbeat]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
