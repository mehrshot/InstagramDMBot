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
    conversations,
    dashboard,
    health,
    instagram,
    knowledge,
    products,
    webhooks,
)
from app.core.config import get_settings
from app.core.queue import ArqQueue, InlineQueue

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.http = httpx.AsyncClient(timeout=20)
    redis = None
    if settings.queue_backend == "inline":
        from app.worker import FUNCTIONS

        app.state.queue = InlineQueue(FUNCTIONS, {"http": app.state.http})
    else:
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        app.state.queue = ArqQueue(redis)
    yield
    await app.state.http.aclose()
    if redis is not None:
        await redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
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
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(account.router, prefix=api_prefix)
    app.include_router(instagram.router, prefix=api_prefix)
    app.include_router(knowledge.router, prefix=api_prefix)
    app.include_router(products.router, prefix=api_prefix)
    app.include_router(conversations.router, prefix=api_prefix)
    app.include_router(dashboard.router, prefix=api_prefix)
    return app


app = create_app()
