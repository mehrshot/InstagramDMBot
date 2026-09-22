from fastapi import APIRouter

from app.api.deps import CurrentShop, CurrentUser, DbSession
from app.models import Shop, User
from app.schemas.auth import ShopOut, ShopUpdate, UserOut

router = APIRouter(tags=["account"])


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user


@router.get("/shop", response_model=ShopOut)
async def get_shop(shop: CurrentShop) -> Shop:
    return shop


@router.patch("/shop", response_model=ShopOut)
async def update_shop(body: ShopUpdate, shop: CurrentShop, db: DbSession) -> Shop:
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(shop, field, value)
    await db.commit()
    await db.refresh(shop)
    return shop
