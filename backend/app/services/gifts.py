"""The sign-up gift: free wallet credit, once per real person rather than once per email.

Signing up alone earns nothing (emails are free to make). The gift comes when the owner links
their Telegram or Bale account to the shop and, when SIGNUP_GIFT_REQUIRES_PHONE is on, has a
verified mobile number. Each of those identities can earn a gift once: they're remembered
(hashed) in `gift_claims`, even after the shop is deleted, so re-linking the same account to a
new shop, or deleting and signing up again, doesn't pay twice.

`check` is called whenever one of the conditions may have become true (an account linked, a
number verified); it is idempotent.
"""

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import secret_digest
from app.core.timeutil import utcnow
from app.models import GiftClaim, Shop, TelegramAdmin, User, WalletEntryKind
from app.services import billing

logger = logging.getLogger(__name__)


def _key(kind: str, value: str) -> str:
    return secret_digest(f"gift:{kind}:{value}")


async def _identities(db: AsyncSession, shop: Shop, owner: User) -> tuple[list[str], str | None]:
    admins = (await db.scalars(select(TelegramAdmin).where(TelegramAdmin.shop_id == shop.id))).all()
    messengers = [_key(a.platform, str(a.telegram_user_id)) for a in admins]
    phone = _key("phone", owner.phone) if owner.phone and owner.phone_verified_at else None
    return messengers, phone


def amount() -> int:
    return get_settings().signup_credit_rial if billing.enabled() else 0


async def status(db: AsyncSession, shop: Shop) -> dict[str, bool | int]:
    """What the panel shows: the gift, and which steps are still missing."""
    owner = await db.get(User, shop.owner_id)
    assert owner is not None
    messengers, phone = await _identities(db, shop, owner)
    return {
        "amount_toman": amount() // 10,
        "granted": shop.signup_gift_at is not None,
        "messenger_linked": bool(messengers),
        "phone_required": get_settings().signup_gift_requires_phone,
        "phone_verified": phone is not None,
    }


async def check(db: AsyncSession, shop: Shop) -> int:
    """Give the gift if the shop just became eligible; returns the rials given (0 if not)."""
    owner = await db.get(User, shop.owner_id)
    if owner is None:
        return 0
    messengers, phone = await _identities(db, shop, owner)
    keys = messengers + ([phone] if phone else [])
    if not keys:
        return 0
    claims = {
        c.key: c for c in (await db.scalars(select(GiftClaim).where(GiftClaim.key.in_(keys)))).all()
    }

    if shop.signup_gift_at is not None:
        # Already gifted: whatever else this shop links can't earn another shop a gift.
        for key in keys:
            if key not in claims:
                db.add(GiftClaim(key=key, shop_id=shop.id))
        await _commit(db)
        return 0

    credit = amount()
    if credit <= 0 or not messengers:
        return 0
    if get_settings().signup_gift_requires_phone and phone is None:
        return 0
    if any(c.shop_id != shop.id for c in claims.values()):
        return 0  # this person (account or number) already got a gift for another shop

    for key in keys:
        if key not in claims:
            db.add(GiftClaim(key=key, shop_id=shop.id))
    shop.signup_gift_at = utcnow()
    if not await _commit(db):
        return 0
    await billing.apply(db, shop, credit, WalletEntryKind.BONUS, "هدیه‌ی شروع کار")
    logger.info("sign-up gift of %s rial given to shop %s", credit, shop.id)
    return credit


async def _commit(db: AsyncSession) -> bool:
    try:
        await db.commit()
    except IntegrityError:  # the same identity claimed concurrently
        await db.rollback()
        return False
    return True


def missing_text(gift: dict[str, bool | int]) -> str:
    """Persian hint for the bot: what's left before the gift (empty if nothing is)."""
    if gift["granted"] or not gift["amount_toman"]:
        return ""
    if gift["phone_required"] and not gift["phone_verified"]:
        return (
            f"🎁 با تأیید شماره موبایلتان {gift['amount_toman']:,} تومان اعتبار هدیه می‌گیرید. "
            "دکمه‌ی «📱 تأیید شماره موبایل» را بزنید."
        ).replace(",", "٬")
    return ""
