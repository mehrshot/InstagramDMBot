"""Wallet top-ups through Zarinpal (payment gateway API v4).

    panel ──POST /billing/topup──► request ──► owner pays on Zarinpal ──► callback ──► verify
                                                                              │
                                                       wallet credited ◄──────┘

A payment is credited exactly once: the callback can be hit again (refresh, a second tab)
and only the first successful verification adds credit.
"""

import logging

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


class Zarinpal:
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


def callback_url() -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/api/v1/billing/zarinpal/callback"


async def start_topup(db: AsyncSession, shop: Shop, amount_rial: int, gateway: Zarinpal) -> str:
    """Create a pending payment; returns the gateway URL to send the owner to."""
    settings = get_settings()
    if not gateway.configured:
        raise PaymentError("درگاه پرداخت هنوز فعال نشده است. با پشتیبانی تماس بگیرید.")
    if not settings.topup_min_rial <= amount_rial <= settings.topup_max_rial:
        raise PaymentError(
            f"مبلغ شارژ باید بین {billing.toman(settings.topup_min_rial)} و "
            f"{billing.toman(settings.topup_max_rial)} باشد."
        )
    authority = await gateway.request(
        amount_rial, callback_url(), f"شارژ کیف پول جواب - {shop.name}"[:250]
    )
    db.add(
        Payment(shop_id=shop.id, gateway="zarinpal", amount_rial=amount_rial, authority=authority)
    )
    await db.commit()
    return gateway.start_url(authority)


async def complete_topup(
    db: AsyncSession, authority: str, status_ok: bool, gateway: Zarinpal
) -> Payment | None:
    """Handle the gateway's redirect back. Credits the wallet once; returns the payment."""
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

    # Claim the payment before crediting, so a parallel callback can't credit it twice.
    payment.status = PaymentStatus.PAID
    payment.ref_id = str(result.get("ref_id") or "")[:64] or None
    payment.card_pan = str(result.get("card_pan") or "")[:32] or None
    payment.paid_at = utcnow()
    await db.commit()
    shop = await db.get(Shop, payment.shop_id)
    if shop is not None:
        await billing.apply(
            db,
            shop,
            payment.amount_rial,
            WalletEntryKind.TOPUP,
            "شارژ کیف پول",
            {"payment_id": str(payment.id), "ref_id": payment.ref_id},
        )
    return payment
