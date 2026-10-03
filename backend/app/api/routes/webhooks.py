import hmac
import json
import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.api.deps import DbSession, JobQueue
from app.core.config import get_settings
from app.models import TelegramBot
from app.services.webhook import parse_messaging_events, verify_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"], include_in_schema=False)


@router.get("/instagram")
async def verify_subscription(
    mode: str = Query(alias="hub.mode"),
    verify_token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge"),
) -> PlainTextResponse:
    """Meta calls this once when the webhook URL is saved in the App Dashboard."""
    expected = get_settings().meta_webhook_verify_token
    if mode != "subscribe" or not expected or verify_token != expected:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    return PlainTextResponse(challenge)


@router.post("/instagram")
async def receive(request: Request, queue: JobQueue) -> dict[str, str]:
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_signature(body, signature, get_settings().meta_app_secret):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid signature")
    payload = _json_object(body)
    if not get_settings().instagram_enabled:
        return {"status": "ignored"}  # Instagram is switched off; acknowledge so Meta stops

    # Only enqueue here: Meta disables webhooks that answer slowly.
    for event in parse_messaging_events(payload):
        await queue.enqueue("process_event", event, job_id=f"event:{event.mid}")
    return {"status": "ok"}


@router.post("/telegram/{bot_id}")
async def receive_telegram(
    bot_id: uuid.UUID, request: Request, db: DbSession, queue: JobQueue
) -> dict[str, str]:
    """Telegram (or Bale) calls this for every update of one of our bots (shared or a shop's
    own). Telegram sends our secret in a header; Bale can't, so its webhook URL carries it."""
    bot = await db.get(TelegramBot, bot_id)
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token") or (
        request.query_params.get("secret", "") if bot is not None and bot.platform == "bale" else ""
    )
    if bot is None or not hmac.compare_digest(secret, bot.webhook_secret):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid secret")
    update = _json_object(await request.body())
    if not bot.is_active:
        return {"status": "ignored"}
    update_id = update.get("update_id")
    await queue.enqueue(
        "process_telegram_update",
        str(bot.id),
        update,
        job_id=f"tg:{bot.id}:{update_id}" if update_id is not None else None,
    )
    return {"status": "ok"}


def _json_object(body: bytes) -> dict:
    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid json") from None
    if not isinstance(payload, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid payload")
    return payload
