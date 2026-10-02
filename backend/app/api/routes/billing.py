"""The shop's wallet (pay as you go), plans, and top-ups through the payment gateway."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.api.deps import CurrentShop, DbSession, HttpClient
from app.core.config import get_settings
from app.models import Plan, WalletEntry, WalletEntryKind
from app.services import billing, payments
from app.services.payments import PaymentError, Zarinpal

router = APIRouter(prefix="/billing", tags=["billing"])


class PlanOut(BaseModel):
    key: Plan
    label: str
    monthly_fee_toman: int
    features: list[str]


class PricingOut(BaseModel):
    """What usage costs (toman). An answer costs by the AI tokens it used, with a minimum."""

    per_1k_prompt_tokens_toman: float
    per_1k_completion_tokens_toman: float
    min_per_answer_toman: float
    per_voice_minute_toman: float
    # A typical answer for a shop with a mid-size catalogue, to set expectations.
    typical_answer_toman: int


class BillingOut(BaseModel):
    # False while billing is switched off on the server (nothing is charged).
    enabled: bool
    balance_toman: int
    low_balance: bool
    plan: Plan
    plan_renews_at: datetime | None
    # A downgrade the owner asked for, applied at plan_renews_at.
    plan_next: Plan | None
    plans: list[PlanOut]
    pricing: PricingOut
    # Whether online top-up (payment gateway) is available.
    topup_available: bool
    topup_min_toman: int
    topup_max_toman: int


class WalletEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: WalletEntryKind
    amount_toman: float
    balance_after_toman: float
    description: str
    details: dict[str, Any]
    created_at: datetime


class WalletEntryPage(BaseModel):
    items: list[WalletEntryOut]
    total: int


class PlanChange(BaseModel):
    plan: Plan


class TopupIn(BaseModel):
    amount_toman: int = Field(gt=0, le=10**9)


class TopupOut(BaseModel):
    # Send the browser here; after paying, Zarinpal returns the owner to FRONTEND_URL/billing
    # with ?payment=success&ref=<bank reference> or ?payment=failed.
    payment_url: str


def get_gateway(http: HttpClient) -> Zarinpal:
    return Zarinpal(http)


@router.get("", response_model=BillingOut)
async def get_billing(shop: CurrentShop) -> BillingOut:
    settings = get_settings()
    return BillingOut(
        enabled=billing.enabled(),
        balance_toman=shop.balance_rial // 10,
        low_balance=billing.enabled() and shop.balance_rial < settings.low_balance_rial,
        plan=shop.plan,
        plan_renews_at=shop.plan_renews_at,
        plan_next=shop.plan_next,
        plans=[
            PlanOut(
                key=info.key,
                label=info.label,
                monthly_fee_toman=billing.plan_fee(info.key) // 10,
                features=info.features,
            )
            for info in billing.PLANS.values()
        ],
        pricing=PricingOut(
            per_1k_prompt_tokens_toman=settings.usage_rial_per_1k_prompt_tokens / 10,
            per_1k_completion_tokens_toman=settings.usage_rial_per_1k_completion_tokens / 10,
            min_per_answer_toman=settings.usage_min_rial_per_reply / 10,
            per_voice_minute_toman=settings.usage_rial_per_voice_minute / 10,
            typical_answer_toman=billing.usage_cost(4000, 150) // 10,
        ),
        topup_available=bool(settings.zarinpal_merchant_id),
        topup_min_toman=settings.topup_min_rial // 10,
        topup_max_toman=settings.topup_max_rial // 10,
    )


@router.get("/entries", response_model=WalletEntryPage)
async def list_entries(
    shop: CurrentShop,
    db: DbSession,
    kind: WalletEntryKind | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> WalletEntryPage:
    """The wallet history, newest first."""
    query = select(WalletEntry).where(WalletEntry.shop_id == shop.id)
    if kind is not None:
        query = query.where(WalletEntry.kind == kind)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(WalletEntry.created_at.desc()).offset(offset).limit(limit)
    )
    return WalletEntryPage(
        items=[
            WalletEntryOut(
                id=e.id,
                kind=e.kind,
                amount_toman=e.amount_rial / 10,
                balance_after_toman=e.balance_after_rial / 10,
                description=e.description,
                details=e.details,
                created_at=e.created_at,
            )
            for e in rows
        ],
        total=total or 0,
    )


@router.post("/plan", response_model=BillingOut)
async def change_plan(body: PlanChange, shop: CurrentShop, db: DbSession) -> BillingOut:
    """Upgrade (starts now, the month's fee is paid from the wallet) or downgrade (applies
    when the paid month ends)."""
    try:
        await billing.change_plan(db, shop, body.plan)
    except billing.BillingError as exc:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, str(exc)) from None
    await db.refresh(shop)
    return await get_billing(shop)


@router.post("/topup", response_model=TopupOut)
async def topup(
    body: TopupIn,
    shop: CurrentShop,
    db: DbSession,
    gateway: Zarinpal = Depends(get_gateway),
) -> TopupOut:
    try:
        url = await payments.start_topup(db, shop, body.amount_toman * 10, gateway)
    except PaymentError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    return TopupOut(payment_url=url)


@router.get("/zarinpal/callback", include_in_schema=False)
async def zarinpal_callback(
    db: DbSession,
    gateway: Zarinpal = Depends(get_gateway),
    authority: str = Query(alias="Authority", default=""),
    payment_status: str = Query(alias="Status", default=""),
) -> RedirectResponse:
    """Zarinpal sends the owner's browser here after paying; we verify and go to the panel."""
    panel = f"{get_settings().frontend_url.rstrip('/')}/billing"
    payment = (
        await payments.complete_topup(db, authority, payment_status == "OK", gateway)
        if authority
        else None
    )
    if payment is not None and payment.status.value == "paid":
        return RedirectResponse(f"{panel}?payment=success&ref={payment.ref_id or ''}")
    return RedirectResponse(f"{panel}?payment=failed")
