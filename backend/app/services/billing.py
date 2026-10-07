"""The shop wallet: pay-as-you-go usage and plan fees.

A shop tops up its wallet; every AI answer is deducted from it by the tokens it used (with a
minimum per answer). Plans above "basic" add a monthly fee, also paid from the wallet. When the
balance runs out the bot stops answering (the customer gets the shop's fallback message and
the conversation goes to the owner) until the owner tops up.

All amounts are integer rials. Every change is a row in the ledger (`WalletEntry`).
"""

import logging
import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.timeutil import as_utc, utcnow
from app.models import Plan, Shop, WalletEntry, WalletEntryKind

logger = logging.getLogger(__name__)

PLAN_PERIOD = timedelta(days=30)
# Don't remind about an empty wallet more often than this.
EMPTY_WALLET_REMINDER = timedelta(hours=12)


class BillingError(Exception):
    """User-facing (Persian) reason a billing action was refused."""


@dataclass(frozen=True)
class PlanInfo:
    key: Plan
    label: str
    features: list[str]
    rank: int


PLANS: dict[Plan, PlanInfo] = {
    Plan.BASIC: PlanInfo(
        Plan.BASIC,
        "پایه",
        [
            "ربات مشترک «جواب» در تلگرام با لینک اختصاصی فروشگاه شما",
            "اینستاگرام (پس از فعال شدن)",
            "پرداخت فقط به اندازه‌ی مصرف",
        ],
        0,
    ),
    Plan.PRO: PlanInfo(
        Plan.PRO,
        "حرفه‌ای",
        [
            "همه‌ی امکانات پلن پایه",
            "ربات تلگرام اختصاصی با نام و عکس فروشگاه شما",
        ],
        1,
    ),
    Plan.BUSINESS: PlanInfo(
        Plan.BUSINESS,
        "بیزینس",
        [
            "همه‌ی امکانات پلن حرفه‌ای",
            "جواب دادن «جواب» از طرف اکانت شخصی تلگرام شما (Telegram Business)",
        ],
        2,
    ),
}


def plan_fee(plan: Plan) -> int:
    settings = get_settings()
    return {
        Plan.BASIC: 0,
        Plan.PRO: settings.plan_pro_monthly_rial,
        Plan.BUSINESS: settings.plan_business_monthly_rial,
    }[plan]


def enabled() -> bool:
    return get_settings().billing_enabled


def usage_cost(prompt_tokens: int, completion_tokens: int) -> int:
    settings = get_settings()
    cost = (
        prompt_tokens * settings.usage_rial_per_1k_prompt_tokens
        + completion_tokens * settings.usage_rial_per_1k_completion_tokens
    ) / 1000
    return max(math.ceil(cost), settings.usage_min_rial_per_reply)


def is_house(shop: Shop) -> bool:
    """Javab's own shop (the website assistant): it answers for us and is never charged."""
    return bool(shop.slug) and shop.slug == get_settings().site_assistant_shop_slug


def can_spend(shop: Shop) -> bool:
    return not enabled() or is_house(shop) or shop.balance_rial > 0


async def apply(
    db: AsyncSession,
    shop: Shop,
    amount_rial: int,
    kind: WalletEntryKind,
    description: str,
    details: dict[str, Any] | None = None,
) -> int:
    """Change the balance by `amount_rial` (negative spends) atomically; returns the new one.

    Commits. The UPDATE is done in SQL so two concurrent answers can't lose a deduction.
    """
    new_balance = await db.scalar(
        update(Shop)
        .where(Shop.id == shop.id)
        .values(balance_rial=Shop.balance_rial + amount_rial)
        .returning(Shop.balance_rial)
        .execution_options(synchronize_session=False)
    )
    assert new_balance is not None
    shop.balance_rial = new_balance
    db.add(
        WalletEntry(
            shop_id=shop.id,
            kind=kind,
            amount_rial=amount_rial,
            balance_after_rial=new_balance,
            description=description[:255],
            details=details or {},
        )
    )
    if amount_rial > 0 and new_balance >= get_settings().low_balance_rial:
        # Topped up: warn again next time it runs low.
        shop.low_balance_notified_at = None
        shop.empty_wallet_notified_at = None
    await db.commit()
    return new_balance


async def charge_usage(
    db: AsyncSession,
    shop: Shop,
    *,
    prompt_tokens: int | None,
    completion_tokens: int | None,
    description: str,
    details: dict[str, Any] | None = None,
) -> bool:
    """Deduct one AI answer. Returns True when the owner should now be told the balance is low."""
    if not enabled() or is_house(shop) or not (prompt_tokens or completion_tokens):
        return False
    prompt, completion = prompt_tokens or 0, completion_tokens or 0
    cost = usage_cost(prompt, completion)
    balance = await apply(
        db,
        shop,
        -cost,
        WalletEntryKind.USAGE,
        description,
        {"prompt_tokens": prompt, "completion_tokens": completion, **(details or {})},
    )
    return await _crossed_low_balance(db, shop, balance)


async def _crossed_low_balance(db: AsyncSession, shop: Shop, balance: int) -> bool:
    if balance >= get_settings().low_balance_rial or shop.low_balance_notified_at is not None:
        return False
    shop.low_balance_notified_at = utcnow()
    await db.commit()
    return True


async def should_remind_empty(db: AsyncSession, shop: Shop) -> bool:
    """True (and recorded) if the owner hasn't been told about the empty wallet recently."""
    last = shop.empty_wallet_notified_at
    if last is not None and utcnow() - as_utc(last) < EMPTY_WALLET_REMINDER:
        return False
    shop.empty_wallet_notified_at = utcnow()
    await db.commit()
    return True


async def change_plan(db: AsyncSession, shop: Shop, plan: Plan) -> None:
    """Upgrades start now and charge the month's fee; downgrades apply when the month ends."""
    current = PLANS[shop.plan]
    target = PLANS[plan]
    if plan == shop.plan:
        shop.plan_next = None  # cancels a scheduled downgrade
        await db.commit()
        return
    if target.rank > current.rank:
        fee = plan_fee(plan)
        if enabled() and shop.balance_rial < fee:
            raise BillingError(
                f"موجودی کیف پول کافی نیست. هزینه‌ی ماهانه‌ی پلن {target.label} "
                f"{fee // 10:,} تومان است."
            )
        if fee and enabled():
            await apply(
                db,
                shop,
                -fee,
                WalletEntryKind.PLAN_FEE,
                f"هزینه‌ی ماهانه‌ی پلن {target.label}",
                {"plan": plan.value},
            )
        shop.plan = plan
        shop.plan_renews_at = utcnow() + PLAN_PERIOD if fee else None
        shop.plan_next = None
    elif shop.plan_renews_at is None:
        shop.plan = plan
        shop.plan_next = None
    else:
        shop.plan_next = plan
    await db.commit()


async def renew_plans(db: AsyncSession) -> list[tuple[Shop, str]]:
    """Charge the next month for shops whose paid month ended, or move them to basic.

    Returns (shop, Persian message for the owner) for shops whose plan changed.
    """
    now = utcnow()
    due = (
        await db.scalars(select(Shop).where(Shop.plan != Plan.BASIC, Shop.plan_renews_at <= now))
    ).all()
    changes: list[tuple[Shop, str]] = []
    for shop in due:
        target = shop.plan_next or shop.plan
        shop.plan_next = None
        fee = plan_fee(target)
        if target == Plan.BASIC or fee == 0:
            shop.plan = target
            shop.plan_renews_at = None
            await db.commit()
            changes.append((shop, f"پلن شما به {PLANS[target].label} تغییر کرد."))
            continue
        if enabled() and shop.balance_rial < fee:
            label = PLANS[shop.plan].label
            shop.plan = Plan.BASIC
            shop.plan_renews_at = None
            await db.commit()
            changes.append(
                (
                    shop,
                    f"موجودی کیف پول برای تمدید پلن {label} کافی نبود و پلن شما به «پایه» "
                    "برگشت. بعد از شارژ کیف پول می‌توانید دوباره آن را فعال کنید.",
                )
            )
            continue
        if enabled():
            await apply(
                db,
                shop,
                -fee,
                WalletEntryKind.PLAN_FEE,
                f"تمدید ماهانه‌ی پلن {PLANS[target].label}",
                {"plan": target.value},
            )
        shop.plan = target
        shop.plan_renews_at = as_utc(shop.plan_renews_at or now) + PLAN_PERIOD
        await db.commit()
    return changes


def toman(rial: int) -> str:
    """Rial amount as a Persian-friendly toman string: "۱۲٬۵۰۰ تومان"."""
    return f"{rial // 10:,} تومان".replace(",", "٬")


def house_facts() -> str:
    """Live prices and plans for Javab's own assistant, so it never quotes stale numbers."""
    settings = get_settings()
    lines = [
        "CURRENT PRICES AND PLANS OF JAVAB (always up to date; prefer these over any other numbers)"
    ]
    if not settings.billing_enabled:
        lines.append("- Javab is free to use right now (billing is switched off).")
    else:
        lines.append(
            f"- Pay as you go: each bot answer costs about {toman(usage_cost(4000, 150))} "
            f"(at least {toman(settings.usage_min_rial_per_reply)}); it depends on how much "
            "text the AI reads and writes. Off-topic questions customers ask are not charged."
        )
        lines.append(
            f"- Wallet top-up between {toman(settings.topup_min_rial)} and "
            f"{toman(settings.topup_max_rial)}; credit is non-refundable."
        )
        gift = settings.signup_credit_rial
        if gift:
            condition = (
                "after linking their Telegram or Bale account and verifying their mobile number"
                if settings.signup_gift_requires_phone
                else "after linking their Telegram or Bale account"
            )
            lines.append(
                f"- New shops get {toman(gift)} of gift credit {condition}, once per person."
            )
    for info in PLANS.values():
        fee = plan_fee(info.key)
        price = f"{toman(fee)} a month" if fee else "no monthly fee"
        lines.append(f"- Plan «{info.label}» ({price}): " + "؛ ".join(info.features))
    return "\n".join(lines)
