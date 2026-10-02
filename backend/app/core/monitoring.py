"""Error monitoring: Sentry (optional) and error alerts to an operations Telegram chat.

Both are off unless configured:
- SENTRY_DSN: errors and their stack traces go to Sentry (or a Sentry-compatible service such
  as a self-hosted GlitchTip).
- OPS_TELEGRAM_CHAT_ID (+ TELEGRAM_BOT_TOKEN): every ERROR log line is also sent by the shared
  bot to that chat, so the team hears about problems on their phones. Repeats of the same
  error are grouped (at most one message per error every 10 minutes).
"""

import hashlib
import logging
import queue
import threading
import time

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_ALERT_REPEAT_SECONDS = 600
_configured = False


def setup_monitoring(component: str) -> None:
    """Call once per process (API or worker)."""
    global _configured
    if _configured:
        return
    _configured = True
    settings = get_settings()
    if settings.sentry_dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment=settings.environment,
                server_name=component,
                traces_sample_rate=0.0,
                send_default_pii=False,
            )
            logger.info("sentry enabled for %s", component)
        except Exception:  # monitoring must never stop the app from starting
            logger.exception("could not start sentry")
    if settings.ops_telegram_chat_id and settings.telegram_bot_token:
        handler = TelegramAlertHandler(
            settings.telegram_bot_token,
            settings.ops_telegram_chat_id,
            settings.telegram_api_base,
            f"{settings.app_name} {component} ({settings.environment})",
        )
        handler.setLevel(logging.ERROR)
        logging.getLogger().addHandler(handler)


class TelegramAlertHandler(logging.Handler):
    """Sends ERROR records to a Telegram chat from a background thread (never blocks)."""

    def __init__(self, token: str, chat_id: str, api_base: str, source: str) -> None:
        super().__init__()
        self._url = f"{api_base.rstrip('/')}/bot{token}/sendMessage"
        self._chat_id = chat_id
        self._source = source
        self._queue: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._last_sent: dict[str, float] = {}
        threading.Thread(target=self._run, name="ops-alerts", daemon=True).start()

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith(("httpx", "httpcore")):
            return  # our own sends; avoids alert loops
        try:
            key = hashlib.sha1(f"{record.name}:{record.msg}".encode()).hexdigest()
            now = time.monotonic()
            if now - self._last_sent.get(key, -_ALERT_REPEAT_SECONDS) < _ALERT_REPEAT_SECONDS:
                return
            self._last_sent[key] = now
            text = self.format(record)
            if record.exc_info:
                text = text[-3000:]
            self._queue.put(f"🚨 {self._source}\n{text}"[:4000])
        except Exception:
            self.handleError(record)

    def _run(self) -> None:
        with httpx.Client(timeout=15) as client:
            while True:
                text = self._queue.get()
                try:
                    client.post(
                        self._url,
                        json={
                            "chat_id": self._chat_id,
                            "text": text,
                            "link_preview_options": {"is_disabled": True},
                        },
                    )
                except Exception:  # alerting is best effort
                    pass
