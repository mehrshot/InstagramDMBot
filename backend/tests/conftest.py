import os

# Must be set before app modules read settings. Ignore any local backend/.env so tests always
# run against these values only.
os.environ["APP_ENV_FILE"] = ""
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
# The suite covers Instagram even while it is switched off in production.
os.environ["INSTAGRAM_ENABLED"] = "true"
# Wallet charging is covered by its own tests (which switch it on).
os.environ["BILLING_ENABLED"] = "false"
# The off-topic check is an extra AI call; covered by its own tests (test_off_topic.py).
os.environ["OFF_TOPIC_GUARD"] = "false"
os.environ["TELEGRAM_API_BASE"] = "https://tg.test"
os.environ["BALE_API_BASE"] = "https://bale.test"
os.environ["ZARINPAL_SANDBOX"] = "true"
os.environ["ABAN_API_BASE"] = "https://aban.test"

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

from app.api.deps import get_http, get_instagram_client, get_queue, get_telegram_client
from app.core.config import get_settings
from app.core.database import get_db
from app.main import app
from app.models import Base
from app.services.instagram import InstagramClient
from app.services.telegram import TelegramClient


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
    # Posts returned by /me/media, served two per page to exercise pagination.
    media: list[dict[str, Any]] = field(default_factory=list)
    # When set, sharing a post (MEDIA_SHARE) fails with this; plain text still works.
    post_error: tuple[int, dict[str, Any]] | None = None
    # Comments: public replies posted, hide/show calls, and posts read one by one.
    public_replies: list[dict[str, str]] = field(default_factory=list)
    hidden: dict[str, bool] = field(default_factory=dict)
    media_info: dict[str, dict[str, Any]] = field(default_factory=dict)
    reply_error: tuple[int, dict[str, Any]] | None = None
    # Stories: containers created, their processing state, and what was published.
    containers: list[dict[str, str]] = field(default_factory=list)
    container_status: str = "FINISHED"
    published: list[str] = field(default_factory=list)
    # Insights: the profile's counts, account totals, daily series and per-post numbers.
    followers: int = 1520
    account_totals: dict[str, int] = field(default_factory=dict)
    series: dict[str, list[int]] = field(default_factory=dict)
    media_numbers: dict[str, dict[str, int]] = field(default_factory=dict)

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        form = (
            {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
            if request.method == "POST"
            and "x-www-form-urlencoded" in request.headers.get("content-type", "")
            else {}
        )
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
        if path.endswith("/me/media"):
            start = int(request.url.params.get("after", 0))
            page: dict[str, Any] = {"data": self.media[start : start + 2]}
            if start + 2 < len(self.media):
                page["paging"] = {
                    "next": f"https://graph.instagram.com/v23.0/me/media?after={start + 2}"
                }
            return httpx.Response(200, json=page)
        if path.endswith("/me/messages"):
            if self.send_error:
                return httpx.Response(self.send_error[0], json=self.send_error[1])
            body = json.loads(request.content)
            if self.post_error and "attachment" in body["message"]:
                return httpx.Response(self.post_error[0], json=self.post_error[1])
            body["token"] = request.headers["Authorization"].removeprefix("Bearer ")
            self.sent.append(body)
            recipient = body["recipient"]
            return httpx.Response(
                200,
                json={
                    "recipient_id": recipient.get("id") or "commenter-igsid",
                    "message_id": f"bot-mid-{len(self.sent)}",
                },
            )
        if path.endswith("/me"):
            return httpx.Response(
                200,
                json={
                    "user_id": self.ig_user_id,
                    "username": self.username,
                    "name": "Layla Boutique",
                    "followers_count": self.followers,
                    "follows_count": 210,
                    "media_count": len(self.media),
                },
            )
        if path.endswith("/replies") and request.method == "POST":
            if self.reply_error:
                return httpx.Response(self.reply_error[0], json=self.reply_error[1])
            self.public_replies.append(
                {"comment_id": path.split("/")[-2], "message": form.get("message", "")}
            )
            return httpx.Response(200, json={"id": f"reply-{len(self.public_replies)}"})
        if path.endswith("/media_publish"):
            self.published.append(form["creation_id"])
            return httpx.Response(200, json={"id": f"story-media-{len(self.published)}"})
        if path.endswith(f"/{self.ig_user_id}/media") and request.method == "POST":
            self.containers.append(form)
            return httpx.Response(200, json={"id": f"container-{len(self.containers)}"})
        if path.endswith(f"/{self.ig_user_id}/insights"):
            params = request.url.params
            metrics = params["metric"].split(",")
            if params.get("metric_type") == "total_value":
                data = [
                    {"name": m, "total_value": {"value": self.account_totals.get(m, 0)}}
                    for m in metrics
                ]
            else:
                data = [
                    {
                        "name": m,
                        "values": [
                            {"value": v, "end_time": f"2026-10-{i + 1:02d}T07:00:00+0000"}
                            for i, v in enumerate(self.series.get(m, []))
                        ],
                    }
                    for m in metrics
                ]
            return httpx.Response(200, json={"data": data})
        if path.endswith("/insights"):
            numbers = self.media_numbers.get(path.split("/")[-2], {})
            return httpx.Response(
                200,
                json={"data": [{"name": k, "values": [{"value": v}]} for k, v in numbers.items()]},
            )
        object_id = path.rsplit("/", 1)[-1]
        if request.method == "POST" and "hide" in form:
            self.hidden[object_id] = form["hide"] == "true"
            return httpx.Response(200, json={"success": True})
        if request.method == "GET" and object_id.startswith("container-"):
            return httpx.Response(200, json={"status_code": self.container_status})
        if request.method == "GET" and object_id in self.media_info:
            return httpx.Response(200, json=self.media_info[object_id])
        return httpx.Response(404, json={"error": {"message": f"unexpected {path}", "code": 100}})

    def client(self) -> InstagramClient:
        return InstagramClient(httpx.AsyncClient(transport=httpx.MockTransport(self.handler)))


@dataclass
class FakeTelegram:
    """The Telegram Bot API (https://tg.test/bot<token>/<method>)."""

    # token -> getMe result
    bots: dict[str, dict[str, Any]] = field(default_factory=dict)
    calls: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)
    # Which server each call went to ("tg.test" or "bale.test"), in the order of `calls`.
    hosts: list[str] = field(default_factory=list)
    # method -> (error_code, description)
    errors: dict[str, tuple[int, str]] = field(default_factory=dict)
    files: dict[str, bytes] = field(default_factory=dict)
    next_message_id: int = 1000

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.startswith("/file/bot"):
            name = path.split("/", 3)[3]
            return httpx.Response(200, content=self.files.get(name, b"audio"))
        token, _, method = path.removeprefix("/bot").partition("/")
        payload = json.loads(request.content or b"{}")
        self.calls.append((token, method, payload))
        self.hosts.append(request.url.host)
        if method in self.errors:
            code, description = self.errors[method]
            return httpx.Response(
                code, json={"ok": False, "error_code": code, "description": description}
            )
        if method == "getMe":
            if token not in self.bots:
                return httpx.Response(
                    401, json={"ok": False, "error_code": 401, "description": "Unauthorized"}
                )
            return httpx.Response(200, json={"ok": True, "result": self.bots[token]})
        if method == "getFile":
            file_id = payload["file_id"]
            return httpx.Response(
                200,
                json={"ok": True, "result": {"file_path": f"files/{file_id}", "file_size": 10}},
            )
        if method in ("sendMessage", "sendPhoto", "copyMessage"):
            self.next_message_id += 1
            return httpx.Response(
                200, json={"ok": True, "result": {"message_id": self.next_message_id}}
            )
        return httpx.Response(200, json={"ok": True, "result": True})

    def sent(self, method: str = "sendMessage") -> list[dict[str, Any]]:
        return [payload for _, m, payload in self.calls if m == method]


@dataclass
class FakeZarinpal:
    """Zarinpal's sandbox payment API."""

    requests: list[dict[str, Any]] = field(default_factory=list)
    verifies: list[dict[str, Any]] = field(default_factory=list)
    verify_code: int = 100

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path.endswith("/request.json"):
            self.requests.append(body)
            return httpx.Response(
                200, json={"data": {"code": 100, "authority": f"A{len(self.requests):035d}"}}
            )
        self.verifies.append(body)
        if self.verify_code not in (100, 101):
            return httpx.Response(200, json={"data": [], "errors": {"code": self.verify_code}})
        return httpx.Response(
            200,
            json={"data": {"code": self.verify_code, "ref_id": 201, "card_pan": "6037****1234"}},
        )


@dataclass
class FakeAban:
    """Aban Gateway's invoice API (card-to-card with automatic confirmation)."""

    invoices: dict[str, dict[str, Any]] = field(default_factory=dict)
    created: list[dict[str, Any]] = field(default_factory=list)
    verifies: list[str] = field(default_factory=list)
    # When set, creating an invoice fails with this (status, error code).
    create_error: tuple[int, str] | None = None

    def pay(self, invoice_id: str) -> None:
        """The owner transferred the exact amount and the bank SMS arrived."""
        self.invoices[invoice_id]["status"] = "paid"

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("authorization") != "Bearer ag_test_token":
            return httpx.Response(401, json={"detail": "bad token"})
        path = request.url.path
        if request.method == "POST" and path == "/api/v1/invoices":
            if self.create_error:
                status, code = self.create_error
                return httpx.Response(status, json={"error": {"code": code, "message": code}})
            body = json.loads(request.content)
            self.created.append(body)
            invoice_id = f"inv_{len(self.created):020d}"
            invoice = {
                "invoice_id": invoice_id,
                "status": "pending",
                "amount_rial": body["amount_rial"],
                "payable_rial": body["amount_rial"] + 3240,
                "order_id": body.get("order_id"),
                "payment_url": f"https://abangateway.ir/pay/{invoice_id}",
                "verified": False,
            }
            self.invoices[invoice_id] = invoice
            return httpx.Response(201, json=invoice)
        parts = path.split("/")  # ['', 'api', 'v1', 'invoices', id, action?]
        invoice = self.invoices.get(parts[4]) if len(parts) > 4 else None
        if invoice is None:
            return httpx.Response(404, json={"error": {"code": "invoice_not_found"}})
        if request.method == "GET":
            return httpx.Response(200, json=invoice)
        if parts[-1] == "verify":
            self.verifies.append(invoice["invoice_id"])
            if invoice["status"] != "paid":
                return httpx.Response(402, json={"error": {"code": "not_yet_paid"}})
            if invoice["verified"]:
                return httpx.Response(409, json={"error": {"code": "already_verified"}})
            invoice["verified"] = True
            return httpx.Response(200, json={"verified": True, **invoice})
        return httpx.Response(404, json={"error": {"code": "invalid_request"}})


class FakeWeb:
    """Google Sheets/Drive downloads, an OpenAI-compatible LLM, Telegram and Zarinpal, behind
    httpx.MockTransport.

    - `files[url] = (status, body, content_type)` serves a Google download URL.
    - `llm_replies` is a queue of assistant messages the fake LLM returns in order.
    """

    def __init__(self) -> None:
        self.telegram = FakeTelegram()
        self.zarinpal = FakeZarinpal()
        self.aban = FakeAban()
        self.files: dict[str, tuple[int, bytes, str]] = {}
        self.llm_replies: list[dict[str, Any]] = []
        self.llm_requests: list[dict[str, Any]] = []
        self.llm_status = 200
        # Parameters the fake model refuses, like newer OpenAI models do with max_tokens.
        self.llm_rejects: set[str] = set()

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.host in ("tg.test", "bale.test"):
            return self.telegram.handler(request)
        if request.url.host == "sandbox.zarinpal.com":
            return self.zarinpal.handler(request)
        if request.url.host == "aban.test":
            return self.aban.handler(request)
        if request.url.host == "llm.test":
            body = json.loads(request.content)
            self.llm_requests.append(body)
            for param in self.llm_rejects & body.keys():
                return httpx.Response(
                    400,
                    json={
                        "error": {
                            "message": f"Unsupported parameter: '{param}' is not supported "
                            "with this model.",
                            "type": "invalid_request_error",
                            "param": param,
                        }
                    },
                )
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
    app.dependency_overrides[get_telegram_client] = lambda: TelegramClient(fake_web.client())
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


@pytest.fixture(autouse=True)
def _fresh_rate_limits() -> None:
    """Rate limits live in memory; every test starts with none used."""
    from app.api.routes import account, auth

    auth.configure_login_throttle()
    for throttle in (
        auth._verify_email_minute,
        auth._verify_email_day,
        account._sms_per_user,
        account._sms_per_phone,
        account._sms_per_user_day,
    ):
        throttle.clear()
    auth._last_reset_request.clear()


@pytest.fixture(autouse=True)
def _email_check_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Most tests use a fresh, unverified sign-up; test_verification covers the closed panel."""
    monkeypatch.setattr(get_settings(), "require_verified_email", False)


@pytest.fixture
def billing_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Charge AI answers to the shop's wallet, as in production."""
    monkeypatch.setattr(get_settings(), "billing_enabled", True)
