"""Background job queue.

Production uses arq on Redis. `InlineQueue` runs jobs as asyncio tasks inside the API
process, so the whole DM pipeline can be exercised locally without Redis.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any, Protocol

from arq import ArqRedis

logger = logging.getLogger(__name__)

JobFunction = Callable[..., Awaitable[Any]]


class Queue(Protocol):
    async def enqueue(
        self, function: str, *args: Any, job_id: str | None = None, defer_seconds: float = 0
    ) -> None: ...


class ArqQueue:
    def __init__(self, redis: ArqRedis) -> None:
        self._redis = redis

    async def enqueue(
        self, function: str, *args: Any, job_id: str | None = None, defer_seconds: float = 0
    ) -> None:
        # arq ignores a job whose id is already queued or recently finished: that is what
        # de-duplicates Meta's webhook retries.
        await self._redis.enqueue_job(
            function,
            *args,
            _job_id=job_id,
            _defer_by=timedelta(seconds=defer_seconds) if defer_seconds else None,
        )


class InlineQueue:
    """In-process queue for local development only: jobs are lost on restart, no retries."""

    def __init__(self, functions: dict[str, JobFunction], ctx: dict[str, Any]) -> None:
        self._functions = functions
        self._ctx = {**ctx, "queue": self, "job_try": 1}
        self._seen: set[str] = set()
        self._tasks: set[asyncio.Task[None]] = set()

    async def enqueue(
        self, function: str, *args: Any, job_id: str | None = None, defer_seconds: float = 0
    ) -> None:
        if job_id is not None:
            if job_id in self._seen:
                return
            self._seen.add(job_id)
        task = asyncio.create_task(self._run(self._functions[function], args, defer_seconds))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, fn: JobFunction, args: tuple[Any, ...], defer_seconds: float) -> None:
        if defer_seconds:
            await asyncio.sleep(defer_seconds)
        try:
            await fn(self._ctx, *args)
        except Exception:
            logger.exception("inline job %s failed", fn.__name__)
