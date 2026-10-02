import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    account,
    auth,
    billing,
    conversations,
    dashboard,
    health,
    instagram,
    knowledge,
    products,
    teach,
    telegram,
    webhooks,
)
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.monitoring import setup_monitoring
from app.core.queue import ArqQueue, InlineQueue
from app.services.telegram import TelegramClient
from app.services.telegram_setup import ensure_shared_bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def _register_shared_bot(http: httpx.AsyncClient) -> None:
    """Point the shared Telegram bot's webhook at this server (idempotent, every start)."""
    try:
        async with SessionLocal() as db:
            await ensure_shared_bot(db, TelegramClient(http))
    except Exception:
        logger.exception("could not register the shared telegram bot")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_monitoring("api")
    app.state.http = httpx.AsyncClient(timeout=20)
    redis = None
    if settings.queue_backend == "inline":
        from app.worker import FUNCTIONS

        app.state.queue = InlineQueue(FUNCTIONS, {"http": app.state.http})
    else:
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        app.state.queue = ArqQueue(redis)
    setup_task = None
    # Telegram only delivers webhooks to public HTTPS addresses; locally, use
    # scripts/telegram_poll.py instead.
    public = settings.public_base_url.startswith("https://")
    if settings.telegram_bot_token and settings.environment != "test" and public:
        setup_task = asyncio.create_task(_register_shared_bot(app.state.http))
    yield
    if setup_task is not None:
        setup_task.cancel()
    await app.state.http.aclose()
    if redis is not None:
        await redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        lifespan=lifespan,
        # Keep interactive docs off the public internet in production.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(webhooks.router)
    api_prefix = "/api/v1"
    for module in (
        auth,
        account,
        instagram,
        telegram,
        knowledge,
        products,
        teach,
        conversations,
        dashboard,
        billing,
    ):
        app.include_router(module.router, prefix=api_prefix)
    return app


app = create_app()
