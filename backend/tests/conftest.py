import os

# Must be set before app modules read settings.
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-123456"
os.environ["ENCRYPTION_KEY"] = "u5Q3pX0cQyJ6c1l0vH1i8wK3rP4mZ2nB7eT9aY6dF0g="
os.environ["META_APP_ID"] = "ig-app-id"
os.environ["META_APP_SECRET"] = "ig-app-secret"
os.environ["META_WEBHOOK_VERIFY_TOKEN"] = "verify-me"
os.environ["PUBLIC_BASE_URL"] = "https://api.test"
os.environ["FRONTEND_URL"] = "https://panel.test"
os.environ["LLM_BASE_URL"] = "https://llm.test/v1"
os.environ["LLM_MODEL"] = "test-model"

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_http, get_instagram_client, get_queue
from app.core.config import get_settings
from app.core.database import get_db
from app.main import app
from app.models import Base
from app.services.instagram import InstagramClient


@dataclass
class QueuedJob:
    function: str
    args: tuple[Any, ...]
    job_id: str | None
    defer_seconds: float


class RecordingQueue:
    def __init__(self) -> None:
        self.jobs: list[QueuedJob] = []

    async def enqueue(
        self, function: str, *args: Any, job_id: str | None = None, defer_seconds: float = 0
    ) -> None:
        self.jobs.append(QueuedJob(function, args, job_id, defer_seconds))


@dataclass
class FakeMeta:
    """Stands in for Meta's servers behind a real InstagramClient (via httpx.MockTransport)."""

    ig_user_id: str = "17841400000000001"
    username: str = "mahsa.boutique"
    sent: list[dict[str, Any]] = field(default_factory=list)
    subscribed: bool = False
    # When set, the send endpoint answers with this (status, body) instead of succeeding.
    send_error: tuple[int, dict[str, Any]] | None = None
    refresh_error: tuple[int, dict[str, Any]] | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.url.host == "api.instagram.com" and path == "/oauth/access_token":
            form = parse_qs(request.content.decode())
            if form["code"][0] == "bad-code":
                return httpx.Response(
                    400,
                    json={"error_type": "OAuthException", "code": 400, "error_message": "bad"},
                )
            return httpx.Response(200, json={"data": [{"access_token": "short-token"}]})
        if path == "/access_token":
            return httpx.Response(200, json={"access_token": "long-token", "expires_in": 5184000})
        if path == "/refresh_access_token":
            if self.refresh_error:
                return httpx.Response(self.refresh_error[0], json=self.refresh_error[1])
            return httpx.Response(
                200, json={"access_token": "refreshed-token", "expires_in": 5184000}
            )
        if path.endswith("/me/subscribed_apps"):
            self.subscribed = True
            return httpx.Response(200, json={"success": True})
        if path.endswith("/me/messages"):
            if self.send_error:
                return httpx.Response(self.send_error[0], json=self.send_error[1])
            body = json.loads(request.content)
            body["token"] = request.headers["Authorization"].removeprefix("Bearer ")
            self.sent.append(body)
            return httpx.Response(
                200,
                json={
                    "recipient_id": body["recipient"]["id"],
                    "message_id": f"bot-mid-{len(self.sent)}",
                },
            )
        if path.endswith("/me"):
            return httpx.Response(200, json={"user_id": self.ig_user_id, "username": self.username})
        return httpx.Response(404, json={"error": {"message": f"unexpected {path}", "code": 100}})

    def client(self) -> InstagramClient:
        return InstagramClient(httpx.AsyncClient(transport=httpx.MockTransport(self.handler)))


class FakeWeb:
    """Google Sheets/Drive downloads and an OpenAI-compatible LLM, behind httpx.MockTransport.

    - `files[url] = (status, body, content_type)` serves a Google download URL.
    - `llm_replies` is a queue of assistant messages the fake LLM returns in order.
    """

    def __init__(self) -> None:
        self.files: dict[str, tuple[int, bytes, str]] = {}
        self.llm_replies: list[dict[str, Any]] = []
        self.llm_requests: list[dict[str, Any]] = []
        self.llm_status = 200

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "llm.test":
            body = json.loads(request.content)
            self.llm_requests.append(body)
            if self.llm_status != 200:
                return httpx.Response(self.llm_status, json={"error": "busy"})
            message = self.llm_replies.pop(0) if self.llm_replies else {"content": "باشه"}
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"role": "assistant", **message}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 20},
                },
            )
        served = self.files.get(str(request.url))
        if served is None:
            return httpx.Response(404, text="not found", headers={"content-type": "text/html"})
        status, content, content_type = served
        return httpx.Response(status, content=content, headers={"content-type": content_type})

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handler))

    @staticmethod
    def tool_call(name: str, arguments: dict[str, Any], call_id: str = "call_1") -> dict[str, Any]:
        return {
            "content": None,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments)},
                }
            ],
        }


@pytest.fixture
def fake_web() -> FakeWeb:
    return FakeWeb()


@pytest.fixture
def llm_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend the server has an AI provider key."""
    monkeypatch.setattr(get_settings(), "llm_api_key", "test-key")


@pytest.fixture
async def sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def db(sessions: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with sessions() as session:
        yield session


@pytest.fixture
def fake_meta() -> FakeMeta:
    return FakeMeta()


@pytest.fixture
def queue() -> RecordingQueue:
    return RecordingQueue()


@pytest.fixture
async def client(
    sessions: async_sessionmaker[AsyncSession],
    fake_meta: FakeMeta,
    fake_web: FakeWeb,
    queue: RecordingQueue,
) -> AsyncIterator[AsyncClient]:
    async def _get_db() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_queue] = lambda: queue
    app.dependency_overrides[get_instagram_client] = fake_meta.client
    app.dependency_overrides[get_http] = fake_web.client
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@shop.ir", "password": "strongpass1", "shop_name": "Mahsa Shop"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
