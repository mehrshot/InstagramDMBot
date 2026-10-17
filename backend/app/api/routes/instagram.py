import logging
from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import delete, select

from app.api.deps import CurrentShop, DbSession, Instagram
from app.core.config import get_settings
from app.core.security import TokenError, create_token, decode_token
from app.models import InstagramAccount, InstagramInsights, InstagramPost, Product, Shop
from app.services.instagram import (
    SCOPE_COMMENTS,
    SCOPE_INSIGHTS,
    SCOPE_MESSAGES,
    SCOPE_PUBLISH,
    InstagramError,
)
from app.services.instagram_accounts import AccountInUseError, connect_account
from app.services.posts import link_products, load_posts, post_key, sync_posts

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/instagram", tags=["instagram"])


class ConnectUrlOut(BaseModel):
    url: str


class BridgeCallbackIn(BaseModel):
    code: str | None = None
    state: str | None = None
    error: str | None = None


class BridgeCallbackOut(BaseModel):
    status: str
    reason: str | None = None


INSTAGRAM_OFF = "اتصال اینستاگرام به‌زودی فعال می‌شود. فعلا از تلگرام استفاده کنید."


class InstagramFeatures(BaseModel):
    messages: bool
    comments: bool
    stories: bool
    insights: bool


class InstagramStatusOut(BaseModel):
    available: bool = True
    connected: bool
    active: bool = False
    username: str | None = None
    ig_user_id: str | None = None
    token_expires_at: datetime | None = None
    features: InstagramFeatures | None = None


@router.get("", response_model=InstagramStatusOut)
async def get_status(shop: CurrentShop, db: DbSession) -> InstagramStatusOut:
    available = get_settings().instagram_enabled
    account = await db.scalar(select(InstagramAccount).where(InstagramAccount.shop_id == shop.id))
    if account is None:
        return InstagramStatusOut(available=available, connected=False)
    return InstagramStatusOut(
        available=available,
        connected=True,
        active=account.is_active,
        username=account.username,
        ig_user_id=account.ig_user_id,
        token_expires_at=account.token_expires_at,
        features=InstagramFeatures(
            messages=account.has_scope(SCOPE_MESSAGES),
            comments=account.has_scope(SCOPE_COMMENTS),
            stories=account.has_scope(SCOPE_PUBLISH),
            insights=account.has_scope(SCOPE_INSIGHTS),
        ),
    )


@router.get("/connect-url", response_model=ConnectUrlOut)
async def connect_url(shop: CurrentShop, instagram: Instagram) -> ConnectUrlOut:
    if not get_settings().instagram_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, INSTAGRAM_OFF)
    token = f"javab:{create_token(shop.id, 'ig_oauth')}"
    return ConnectUrlOut(url=instagram.authorize_url(token))


@router.post("/bridge-exchange", response_model=BridgeCallbackOut, include_in_schema=False)
async def bridge_exchange(
    payload: BridgeCallbackIn,
    db: DbSession,
    instagram: Instagram,
) -> BridgeCallbackOut:
    if payload.error:
        return BridgeCallbackOut(status="denied")
    if not payload.code or not payload.state:
        return BridgeCallbackOut(status="error", reason="missing_code")
    raw_state = payload.state.removeprefix("javab:")
    try:
        shop_id = decode_token(raw_state, "ig_oauth")
    except TokenError:
        return BridgeCallbackOut(status="error", reason="invalid_state")
    shop = await db.get(Shop, shop_id)
    if shop is None:
        return BridgeCallbackOut(status="error", reason="invalid_state")

    code = payload.code.removesuffix("#_")
    try:
        await connect_account(db, shop, code, instagram)
    except AccountInUseError:
        return BridgeCallbackOut(status="error", reason="account_in_use")
    except InstagramError as exc:
        logger.warning("instagram connect failed for shop %s: %s", shop.id, exc)
        return BridgeCallbackOut(status="error", reason="instagram")
    return BridgeCallbackOut(status="connected")


@router.get("/callback", include_in_schema=False)
async def callback(
    db: DbSession,
    instagram: Instagram,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    res = await bridge_exchange(
        BridgeCallbackIn(code=code, state=state, error=error),
        db=db,
        instagram=instagram,
    )
    return _back_to_panel(res.status, res.reason)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(shop: CurrentShop, db: DbSession) -> None:
    await db.execute(delete(InstagramAccount).where(InstagramAccount.shop_id == shop.id))
    await db.execute(delete(InstagramPost).where(InstagramPost.shop_id == shop.id))
    await db.execute(delete(InstagramInsights).where(InstagramInsights.shop_id == shop.id))
    await db.commit()


def _back_to_panel(result: str, reason: str | None = None) -> RedirectResponse:
    params = {"status": result} | ({"reason": reason} if reason else {})
    base = get_settings().frontend_url.rstrip("/")
    return RedirectResponse(f"{base}/instagram/callback?{urlencode(params)}", status_code=302)


class PostOut(BaseModel):
    permalink: str
    caption: str
    preview_url: str | None
    media_type: str
    posted_at: datetime | None
    products: list[str]


class PostsOut(BaseModel):
    synced_at: datetime | None
    total: int
    products_without_post: list[str]
    items: list[PostOut]


@router.get("/posts", response_model=PostsOut)
async def list_posts(shop: CurrentShop, db: DbSession) -> PostsOut:
    account = await db.scalar(select(InstagramAccount).where(InstagramAccount.shop_id == shop.id))
    all_posts = await load_posts(db, shop.id)
    items = (await db.scalars(select(Product).where(Product.shop_id == shop.id))).all()
    links = link_products(list(items), all_posts)

    products_by_post: dict[str, list[str]] = {}
    for name, link in links.items():
        products_by_post.setdefault(post_key(link.permalink) or link.permalink, []).append(name)
    names = list(dict.fromkeys(p.name.strip() for p in items))

    newest = sorted(all_posts, key=lambda p: p.posted_at or datetime.min.replace(tzinfo=UTC))
    return PostsOut(
        synced_at=account.posts_synced_at if account else None,
        total=len(all_posts),
        products_without_post=[n for n in names if n not in links],
        items=[
            PostOut(
                permalink=p.permalink,
                caption=p.caption[:300],
                preview_url=p.preview_url,
                media_type=p.media_type,
                posted_at=p.posted_at,
                products=products_by_post.get(post_key(p.permalink) or p.permalink, []),
            )
            for p in reversed(newest[-60:])
        ],
    )


@router.post("/posts/sync", response_model=PostsOut)
async def sync_posts_now(shop: CurrentShop, db: DbSession, instagram: Instagram) -> PostsOut:
    account = await db.scalar(select(InstagramAccount).where(InstagramAccount.shop_id == shop.id))
    if account is None or not account.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "اول پیج اینستاگرام را وصل کنید.")
    try:
        await sync_posts(db, account, instagram)
    except InstagramError as exc:
        logger.warning("post sync failed for shop %s: %s", shop.id, exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "خواندن پست‌ها از اینستاگرام ممکن نشد. کمی بعد دوباره امتحان کنید.",
        ) from None
    return await list_posts(shop, db)
