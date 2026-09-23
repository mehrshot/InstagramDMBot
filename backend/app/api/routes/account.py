from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentShop, CurrentUser, DbSession
from app.core.security import hash_password, verify_password
from app.models import Shop, User
from app.schemas.auth import ShopOut, ShopUpdate, UserOut
from app.services.accounts import delete_user

router = APIRouter(tags=["account"])


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class AccountDelete(BaseModel):
    password: str


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(body: PasswordChange, user: CurrentUser, db: DbSession) -> None:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "رمز عبور فعلی اشتباه است")
    user.password_hash = hash_password(body.new_password)
    await db.commit()


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(body: AccountDelete, user: CurrentUser, db: DbSession) -> None:
    """Permanently delete the account and everything stored for it (Meta requires this)."""
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "رمز عبور اشتباه است")
    await delete_user(db, user.id)


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
