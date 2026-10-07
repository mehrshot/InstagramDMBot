"""Outgoing email over SMTP. Without SMTP_HOST, messages are only logged (development).

Every email has a plain-text part and an HTML part (right-to-left, one button), so it reads
well everywhere and spam filters see a normal message. Test the setup with
`python -m scripts.send_test_email you@example.com`.
"""

import asyncio
import html
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def action_email(*, title: str, intro: str, button: str, link: str, note: str) -> tuple[str, str]:
    """(plain text, HTML) of a one-button email such as "verify your email"."""
    text = f"سلام،\n\n{intro}\n{link}\n\n{note}\n\n«جواب»"
    e = html.escape
    page = f"""<!doctype html>
<html lang="fa" dir="rtl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{e(title)}</title></head>
<body style="margin:0;padding:0;background:#f4f2fb;font-family:Tahoma,Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f2fb;padding:32px 12px;">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#ffffff;border-radius:16px;padding:32px 28px;text-align:right;direction:rtl;">
<tr><td style="font-size:22px;font-weight:bold;color:#5b3fd9;padding-bottom:20px;">جواب</td></tr>
<tr><td style="font-size:18px;font-weight:bold;color:#1c1830;padding-bottom:12px;">{e(title)}</td></tr>
<tr><td style="font-size:15px;line-height:28px;color:#3d3a4f;padding-bottom:24px;">{e(intro)}</td></tr>
<tr><td style="padding-bottom:24px;">
<a href="{e(link)}" style="display:inline-block;background:#6d4ff0;color:#ffffff;text-decoration:none;font-size:15px;font-weight:bold;padding:12px 28px;border-radius:10px;">{e(button)}</a>
</td></tr>
<tr><td style="font-size:13px;line-height:24px;color:#77738a;padding-bottom:8px;">{e(note)}</td></tr>
<tr><td style="font-size:12px;line-height:22px;color:#9a97ab;direction:ltr;text-align:left;word-break:break-all;">{e(link)}</td></tr>
</table>
</td></tr></table>
</body></html>"""
    return text, page


async def send_email(to: str, subject: str, body: str, html_body: str | None = None) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        logger.info("email not sent (SMTP_HOST is empty) to %s: %s\n%s", to, subject, body)
        return
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=False)
    domain = settings.smtp_from.rsplit("@", 1)[-1].strip(" >") or None
    message["Message-ID"] = make_msgid(domain=domain)
    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    await asyncio.to_thread(_send, message)


def _send(message: EmailMessage) -> None:
    settings = get_settings()
    if settings.smtp_ssl:
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20)
    else:
        smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
    with smtp:
        if settings.smtp_starttls and not settings.smtp_ssl:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
