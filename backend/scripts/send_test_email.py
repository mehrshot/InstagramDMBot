"""Send a test email with the server's SMTP settings, to check the setup.

    uv run python -m scripts.send_test_email you@example.com
    (on the server: docker compose exec api python -m scripts.send_test_email you@example.com)

Prints what went wrong if the provider refuses (wrong password, blocked port...).
"""

import asyncio
import sys

from app.core.config import get_settings
from app.services.email import action_email, send_email


async def main(to: str) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        raise SystemExit("SMTP_HOST is empty in the .env file")
    print(f"Sending through {settings.smtp_host}:{settings.smtp_port} as {settings.smtp_from}")
    text, page = action_email(
        title="ایمیل آزمایشی «جواب»",
        intro="اگر این ایمیل را می‌بینید، ارسال ایمیل سرور درست تنظیم شده است.",
        button="رفتن به پنل",
        link=settings.frontend_url,
        note="این یک ایمیل آزمایشی است.",
    )
    await send_email(to, "ایمیل آزمایشی «جواب»", text, page)
    print("Sent. Check the inbox (and the spam folder).")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m scripts.send_test_email you@example.com")
    asyncio.run(main(sys.argv[1]))
