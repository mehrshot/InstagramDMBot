"""Wallet top-ups through a payment gateway: Aban Gateway (default) or Zarinpal.

Aban Gateway is card-to-card with automatic confirmation: the owner transfers the exact
amount shown to a card, Aban reads the bank SMS and tells us by a signed webhook.

    panel ──POST /billing/topup──► invoice ──► owner transfers on Aban's page
                                                  │
           webhook (invoice.paid) / owner returns / hourly check
                                                  ▼
                                   verify with Aban ──► wallet credited (once)

Zarinpal is a classic bank gateway: request ──► pay ──► callback ──► verify.

A payment is credited exactly once: it is claimed (status PAID) before crediting, and the
gateway's own verify call succeeds only once.
"""

import hashlib
import hmac
import logging
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.timeutil import utcnow
from app.models import Payment, PaymentStatus, Shop, WalletEntryKind
from app.services import billing

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """User-facing (Persian) reason a payment could not start or complete."""


# ---------------------------------------------------------------------------- Aban Gateway


class AbanError(PaymentError):
    def __init__(self, message: str, code: str = "", status: int = 0) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


# What the owner is told for Aban's error codes (the rest get a general message).
_ABAN_MESSAGES = {
    "amount_not_allowed": "این مبلغ را درگاه نمی‌پذیرد؛ مبلغ دیگری امتحان کنید.",
    "capacity_full": "درگاه پرداخت الان شلوغ است؛ چند دقیقه‌ی دیگر دوباره تلاش کنید.",
    "cards_at_ceiling": "درگاه پرداخت امروز به سقفش رسیده؛ کمی بعد یا فردا دوباره تلاش کنید.",
}
# Codes that mean our gateway account needs attention (logged as errors so the team hears).
_ABAN_OUR_PROBLEM = {"insufficient_fee_wallet", "no_card_registered", "unsafe_callback_url"}


class AbanGateway:
    name = "aban"

    def __init__(self, http: httpx.AsyncClient, settings: Settings | None = None) -> None:
        self._http = http
        self._settings = settings or get_settings()

    @property
    def configured(self) -> bool:
        return bool(self._settings.aban_api_token and self._settings.aban_webhook_secret)

    @property
    def is_test(self) -> bool:
        return self._settings.aban_api_token.startswith("ag_test_")

    def signature_ok(self, raw: bytes, sent: str) -> bool:
        """The webhook's X-Signature: HMAC-SHA256 of the raw body with our webhook secret."""
        secret = self._settings.aban_webhook_secret
        if not secret or not sent:
            return False
        mine = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        return hmac.compare_digest(mine, sent)

    async def create_invoice(
        self, amount_rial: int, order_id: str, callback_url: str, return_url: str, description: str
    ) -> dict[str, Any]:
        return await self._call(
            "POST",
            "/api/v1/invoices",
            {
                "amount_rial": amount_rial,
                "order_id": order_id,
                "callback_url": callback_url,
                "return_url": return_url,
                "description": description[:1000],
                "expiry_minutes": self._settings.aban_invoice_minutes,
            },
        )

    async def get_invoice(self, invoice_id: str) -> dict[str, Any]:
        return await self._call("GET", f"/api/v1/invoices/{invoice_id}")

    async def verify(self, invoice_id: str) -> dict[str, Any] | None:
        """Confirm a paid invoice. Returns its data if paid (now or before), None if not yet."""
        try:
            return await self._call("POST", f"/api/v1/invoices/{invoice_id}/verify")
        except AbanError as exc:
            if exc.code == "already_verified":
                return {"verified": True, "already": True}
            if exc.code == "not_yet_paid":
                return None
            raise

    async def _call(self, method: str, path: str, body: dict | None = None) -> dict[str, Any]:
        url = self._settings.aban_api_base.rstrip("/") + path
        try:
            resp = await self._http.request(
                method,
                url,
                json=body,
                headers={"Authorization": f"Bearer {self._settings.aban_api_token}"},
                timeout=20,
            )
        except httpx.HTTPError as exc:
            raise AbanError("ارتباط با درگاه پرداخت برقرار نشد؛ کمی بعد دوباره تلاش کنید.") from exc
        try:
            data = resp.json() if resp.content else {}
        except ValueError:
            data = {}
        if resp.status_code < 400 and isinstance(data, dict):
            return data
        error = data.get("error") if isinstance(data, dict) else None
        code = str(error.get("code") or "") if isinstance(error, dict) else ""
        if code in _ABAN_OUR_PROBLEM or resp.status_code == 401:
            logger.error(
                "Aban Gateway refused %s %s: HTTP %s %s", method, path, resp.status_code, data
            )
        else:
            logger.warning("Aban Gateway %s %s: HTTP %s %s", method, path, resp.status_code, data)
        raise AbanError(
            _ABAN_MESSAGES.get(code, "درگاه پرداخت فعلا در دسترس نیست؛ کمی بعد دوباره تلاش کنید."),
            code=code,
            status=resp.status_code,
        )


# ---------------------------------------------------------------------------- Zarinpal


class Zarinpal:
    name = "zarinpal"

    def __init__(self, http: httpx.AsyncClient, settings: Settings | None = None) -> None:
        self._http = http
        self._settings = settings or get_settings()

    @property
    def configured(self) -> bool:
        return bool(self._settings.zarinpal_merchant_id)

    @property
    def _host(self) -> str:
        sandbox = self._settings.zarinpal_sandbox
        return "https://sandbox.zarinpal.com" if sandbox else "https://payment.zarinpal.com"

    def start_url(self, authority: str) -> str:
        return f"{self._host}/pg/StartPay/{authority}"

    async def request(self, amount_rial: int, callback_url: str, description: str) -> str:
        data = await self._post(
            "/pg/v4/payment/request.json",
            {
                "merchant_id": self._settings.zarinpal_merchant_id,
                "amount": amount_rial,
                "currency": "IRR",
                "callback_url": callback_url,
                "description": description,
            },
        )
        authority = data.get("authority")
        if data.get("code") != 100 or not authority:
            raise PaymentError("درگاه پرداخت درخواست را نپذیرفت؛ کمی بعد دوباره تلاش کنید.")
        return str(authority)

    async def verify(self, amount_rial: int, authority: str) -> dict:
        """Returns the gateway's data; code 100 (paid now) or 101 (already verified) = paid."""
        return await self._post(
            "/pg/v4/payment/verify.json",
            {
                "merchant_id": self._settings.zarinpal_merchant_id,
                "amount": amount_rial,
                "authority": authority,
            },
        )

    async def _post(self, path: str, body: dict) -> dict:
        try:
            resp = await self._http.post(self._host + path, json=body, timeout=30)
        except httpx.HTTPError as exc:
            raise PaymentError("ارتباط با درگاه پرداخت برقرار نشد.") from exc
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or not data:
            # Errors come as {"data": [], "errors": {"code": -9, "message": ...}}
            errors = payload.get("errors") if isinstance(payload, dict) else None
            code = errors.get("code") if isinstance(errors, dict) else None
            return {"code": code}
        return data


# ---------------------------------------------------------------------------- top-ups


def _api_url(path: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/api/v1/billing/{path}"


def callback_url() -> str:
    return _api_url("zarinpal/callback")


def gateway_for(http: httpx.AsyncClient) -> AbanGateway | Zarinpal:
    """The gateway this server takes top-ups with (PAYMENT_GATEWAY)."""
    if get_settings().payment_gateway.strip().lower() == "zarinpal":
        return Zarinpal(http)
    return AbanGateway(http)


def _check_amount(amount_rial: int) -> None:
    settings = get_settings()
    if not settings.topup_min_rial <= amount_rial <= settings.topup_max_rial:
        raise PaymentError(
            f"مبلغ شارژ باید بین {billing.toman(settings.topup_min_rial)} و "
            f"{billing.toman(settings.topup_max_rial)} باشد."
        )


async def start_topup(
    db: AsyncSession, shop: Shop, amount_rial: int, gateway: AbanGateway | Zarinpal
) -> str:
    """Create a pending payment; returns the gateway URL to send the owner to."""
    if not gateway.configured:
        raise PaymentError("درگاه پرداخت هنوز فعال نشده است. با پشتیبانی تماس بگیرید.")
    _check_amount(amount_rial)
    description = f"شارژ کیف پول جواب - {shop.name}"
    if isinstance(gateway, Zarinpal):
        authority = await gateway.request(amount_rial, callback_url(), description[:250])
        db.add(
            Payment(
                shop_id=shop.id, gateway="zarinpal", amount_rial=amount_rial, authority=authority
            )
        )
        await db.commit()
        return gateway.start_url(authority)

    payment = Payment(shop_id=shop.id, gateway="aban", amount_rial=amount_rial)
    db.add(payment)
    await db.commit()
    try:
        invoice = await gateway.create_invoice(
            amount_rial,
            order_id=str(payment.id),
            callback_url=_api_url("aban/webhook"),
            return_url=_api_url(f"aban/return/{payment.id}"),
            description=description,
        )
    except PaymentError as exc:
        payment.status = PaymentStatus.FAILED
        payment.error = str(exc)
        await db.commit()
        raise
    payment.authority = str(invoice.get("invoice_id") or "")[:64] or None
    await db.commit()
    url = invoice.get("payment_url")
    if not payment.authority or not url:
        raise PaymentError("درگاه پرداخت پاسخ درستی نداد؛ کمی بعد دوباره تلاش کنید.")
    return str(url)


async def _credit(db: AsyncSession, payment: Payment, ref_id: str | None) -> bool:
    """Mark paid and credit the wallet; False if another request already did."""
    if payment.status == PaymentStatus.PAID:
        return False
    # Claim the payment before crediting, so a parallel request can't credit it twice.
    payment.status = PaymentStatus.PAID
    payment.ref_id = (ref_id or "")[:64] or None
    payment.paid_at = utcnow()
    payment.error = None
    await db.commit()
    shop = await db.get(Shop, payment.shop_id)
    if shop is not None:
        await billing.apply(
            db,
            shop,
            payment.amount_rial,
            WalletEntryKind.TOPUP,
            "شارژ کیف پول",
            {"payment_id": str(payment.id), "gateway": payment.gateway, "ref_id": payment.ref_id},
        )
    return True


async def settle_aban(db: AsyncSession, payment: Payment, gateway: AbanGateway) -> bool:
    """Verify an Aban invoice and credit it if paid. True if the wallet was credited now."""
    if payment.gateway != "aban" or not payment.authority:
        return False
    if payment.status != PaymentStatus.PENDING:
        return False
    try:
        result = await gateway.verify(payment.authority)
    except AbanError as exc:
        if exc.code in ("invoice_expired", "invoice_not_payable", "invoice_not_found"):
            payment.status = PaymentStatus.FAILED
            payment.error = "مهلت پرداخت تمام شد یا فاکتور لغو شد."
            await db.commit()
        else:
            logger.warning("aban verify failed for payment %s: %s", payment.id, exc.code)
        return False
    if result is None:
        return False  # not paid yet
    return await _credit(db, payment, payment.authority)


async def aban_webhook(
    db: AsyncSession, event: dict[str, Any], gateway: AbanGateway
) -> Payment | None:
    """A signed event from Aban (the caller checked the signature). Idempotent.

    Returns the payment if this call credited it (to tell the owner), else None.
    """
    invoice_id = str(event.get("invoice_id") or "")
    if not invoice_id:
        return None
    payment = await db.scalar(
        select(Payment).where(Payment.gateway == "aban", Payment.authority == invoice_id)
    )
    if payment is None or payment.status != PaymentStatus.PENDING:
        return None
    kind = str(event.get("event") or "")
    if kind == "invoice.paid":
        return payment if await settle_aban(db, payment, gateway) else None
    if kind in ("invoice.expired", "invoice.cancelled"):
        payment.status = PaymentStatus.FAILED
        payment.error = "مهلت پرداخت تمام شد." if kind == "invoice.expired" else "فاکتور لغو شد."
        await db.commit()
    return None


async def reconcile_aban(db: AsyncSession, gateway: AbanGateway) -> list[Payment]:
    """Safety net for lost webhooks: settle pending Aban payments from the last two days.

    Returns the payments credited now.
    """
    if not gateway.configured:
        return []
    now = utcnow()
    pending = (
        await db.scalars(
            select(Payment).where(
                Payment.gateway == "aban",
                Payment.status == PaymentStatus.PENDING,
                Payment.authority.is_not(None),
                Payment.created_at > now - timedelta(days=2),
                Payment.created_at < now - timedelta(minutes=2),
            )
        )
    ).all()
    credited = []
    for payment in pending:
        try:
            invoice = await gateway.get_invoice(str(payment.authority))
        except AbanError:
            continue
        status = invoice.get("status")
        if status == "paid":
            if await settle_aban(db, payment, gateway):
                credited.append(payment)
        elif status in ("expired", "cancelled"):
            payment.status = PaymentStatus.FAILED
            payment.error = "مهلت پرداخت تمام شد." if status == "expired" else "فاکتور لغو شد."
            await db.commit()
    return credited


async def complete_topup(
    db: AsyncSession, authority: str, status_ok: bool, gateway: Zarinpal
) -> Payment | None:
    """Handle Zarinpal's redirect back. Credits the wallet once; returns the payment."""
    payment = await db.scalar(select(Payment).where(Payment.authority == authority))
    if payment is None:
        return None
    if payment.status != PaymentStatus.PENDING:
        return payment
    if not status_ok:
        payment.status = PaymentStatus.FAILED
        payment.error = "پرداخت توسط کاربر لغو شد یا ناموفق بود."
        await db.commit()
        return payment
    try:
        result = await gateway.verify(payment.amount_rial, authority)
    except PaymentError as exc:
        # Leave it pending: verifying again later (another callback hit) can still succeed.
        logger.warning("zarinpal verify failed for payment %s: %s", payment.id, exc)
        return payment
    if result.get("code") not in (100, 101):
        payment.status = PaymentStatus.FAILED
        payment.error = f"تایید پرداخت ناموفق بود (کد {result.get('code')})."
        await db.commit()
        return payment
    payment.card_pan = str(result.get("card_pan") or "")[:32] or None
    await _credit(db, payment, str(result.get("ref_id") or ""))
    return payment
