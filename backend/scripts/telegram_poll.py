"""Run the Telegram bots on your own computer, without a public server (long polling).

    uv run python -m scripts.telegram_poll

Needs TELEGRAM_BOT_TOKEN in backend/.env (from @BotFather), and a VPN/proxy if Telegram is
blocked where you are. It takes the bots' updates directly instead of through the webhook, and
answers through the same code the server uses; replies run in this process (inline queue).

Stop the server's webhook use while this runs: polling removes the bots' webhooks. On the
real server the webhook is set again automatically when the API starts.
"""

import asyncio
import logging

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.queue import InlineQueue
from app.core.security import decrypt_secret
from app.models import TelegramBot
from app.services.telegram import TelegramClient, TelegramError
from app.services.telegram_setup import ensure_shared_bot
from app.worker import FUNCTIONS, process_telegram_update

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("telegram_poll")


async def poll(bot_id: str, token: str, username: str, ctx: dict) -> None:
    client = TelegramClient(ctx["http"])
    await client.delete_webhook(token)
    logger.info("polling @%s", username)
    offset = 0
    while True:
        try:
            updates = await client.get_updates(token, offset)
        except TelegramError as exc:
            logger.warning("@%s: %s; retrying in 5s", username, exc)
            await asyncio.sleep(5)
            continue
        for update in updates:
            offset = max(offset, int(update["update_id"]) + 1)
            try:
                await process_telegram_update(ctx, bot_id, update)
            except Exception:
                logger.exception("update %s failed", update.get("update_id"))


async def main() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set in backend/.env")
    async with httpx.AsyncClient(timeout=40) as http:
        ctx: dict = {"http": http, "job_try": 1}
        ctx["queue"] = InlineQueue(FUNCTIONS, ctx)
        async with SessionLocal() as db:
            await ensure_shared_bot(db, TelegramClient(http), set_webhook=False)
            bots = (
                await db.scalars(select(TelegramBot).where(TelegramBot.is_active.is_(True)))
            ).all()
            targets = [(str(b.id), decrypt_secret(b.token_encrypted), b.username) for b in bots]
        await asyncio.gather(*(poll(*target, ctx) for target in targets))


if __name__ == "__main__":
    asyncio.run(main())
