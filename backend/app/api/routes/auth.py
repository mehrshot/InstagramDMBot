from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession
from app.core.security import (
    TokenError,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import Shop, User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens_for(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_token(user.id, "access"),
        refresh_token=create_token(user.id, "refresh"),
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: DbSession) -> TokenPair:
    email_taken = HTTPException(status.HTTP_409_CONFLICT, "این ایمیل قبلا ثبت شده است")
    if await db.scalar(select(User.id).where(User.email == body.email)):
        raise email_taken

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
    )
    user.shop = Shop(name=body.shop_name.strip())
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:  # concurrent registration with the same email
        await db.rollback()
        raise email_taken from None
    return _tokens_for(user)


@router.post("/login", response_model=TokenPair)
async def login(body: LoginRequest, db: DbSession) -> TokenPair:
    user = await db.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "ایمیل یا رمز عبور اشتباه است")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "حساب کاربری غیرفعال است")
    return _tokens_for(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, db: DbSession) -> TokenPair:
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "توکن نامعتبر است")
    try:
        user_id = decode_token(body.refresh_token, "refresh")
    except TokenError:
        raise invalid from None
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise invalid
    return _tokens_for(user)
