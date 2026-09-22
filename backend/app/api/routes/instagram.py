import logging
from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import delete, select

from app.api.deps import CurrentShop, DbSession, Instagram
from app.core.config import get_settings
from app.core.security import TokenError, create_token, decode_token
from app.models import InstagramAccount, Shop
from app.services.instagram import InstagramError
from app.services.instagram_accounts import AccountInUseError, connect_account

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/instagram", tags=["instagram"])


class ConnectUrlOut(BaseModel):
    url: str


class InstagramStatusOut(BaseModel):
    connected: bool
    # False when Meta revoked access (password change, app removed): owner must reconnect.
    active: bool = False
    username: str | None = None
    ig_user_id: str | None = None
    token_expires_at: datetime | None = None


@router.get("", response_model=InstagramStatusOut)
async def get_status(shop: CurrentShop, db: DbSession) -> InstagramStatusOut:
    account = await db.scalar(select(InstagramAccount).where(InstagramAccount.shop_id == shop.id))
    if account is None:
        return InstagramStatusOut(connected=False)
    return InstagramStatusOut(
        connected=True,
        active=account.is_active,
        username=account.username,
        ig_user_id=account.ig_user_id,
        token_expires_at=account.token_expires_at,
    )


@router.get("/connect-url", response_model=ConnectUrlOut)
async def connect_url(shop: CurrentShop, instagram: Instagram) -> ConnectUrlOut:
    """URL of Instagram's consent screen. The panel sends the browser there."""
    return ConnectUrlOut(url=instagram.authorize_url(create_token(shop.id, "ig_oauth")))


@router.get("/callback", include_in_schema=False)
async def callback(
    db: DbSession,
    instagram: Instagram,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Instagram redirects the browser here; we finish the connection and bounce to the panel.

    This request carries no auth header, so the shop is identified by the signed `state`.
    """
    if error:
        return _back_to_panel("denied")
    if not code or not state:
        return _back_to_panel("error", "missing_code")
    try:
        shop_id = decode_token(state, "ig_oauth")
    except TokenError:
        return _back_to_panel("error", "invalid_state")
    shop = await db.get(Shop, shop_id)
    if shop is None:
        return _back_to_panel("error", "invalid_state")

    # Instagram appends "#_" to the code in some redirects.
    code = code.removesuffix("#_")
    try:
        await connect_account(db, shop, code, instagram)
    except AccountInUseError:
        return _back_to_panel("error", "account_in_use")
    except InstagramError as exc:
        logger.warning("instagram connect failed for shop %s: %s", shop.id, exc)
        return _back_to_panel("error", "instagram")
    return _back_to_panel("connected")


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(shop: CurrentShop, db: DbSession) -> None:
    await db.execute(delete(InstagramAccount).where(InstagramAccount.shop_id == shop.id))
    await db.commit()


def _back_to_panel(result: str, reason: str | None = None) -> RedirectResponse:
    params = {"status": result} | ({"reason": reason} if reason else {})
    base = get_settings().frontend_url.rstrip("/")
    return RedirectResponse(f"{base}/instagram/callback?{urlencode(params)}", status_code=302)
