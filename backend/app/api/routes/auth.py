import logging
import time

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession
from app.core.config import get_settings
from app.core.security import (
    TokenError,
    create_password_reset_token,
    create_token,
    decode_token,
    hash_password,
    read_password_reset_token,
    reset_token_matches,
    verify_password,
)
from app.models import Shop, User, WalletEntryKind
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPair
from app.services import billing
from app.services.email import send_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# One reset email per address per minute, so the endpoint can't be used to spam someone.
_RESET_INTERVAL_SECONDS = 60
_last_reset_request: dict[str, float] = {}


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=2000)
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordOut(BaseModel):
    message: str


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
    credit = get_settings().signup_credit_rial
    if billing.enabled() and credit > 0:
        await billing.apply(db, user.shop, credit, WalletEntryKind.BONUS, "هدیه‌ی ثبت‌نام")
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


@router.post(
    "/password/forgot", response_model=ForgotPasswordOut, status_code=status.HTTP_202_ACCEPTED
)
async def forgot_password(body: ForgotPasswordRequest, db: DbSession) -> ForgotPasswordOut:
    """Email a password reset link. Same answer whether or not the email is registered,
    so the endpoint doesn't reveal who has an account."""
    answer = ForgotPasswordOut(
        message="اگر این ایمیل در «جواب» ثبت شده باشد، لینک تغییر رمز برایش فرستاده شد."
    )
    now = time.monotonic()
    if now - _last_reset_request.get(body.email, -_RESET_INTERVAL_SECONDS) < (
        _RESET_INTERVAL_SECONDS
    ):
        return answer
    _last_reset_request[body.email] = now

    user = await db.scalar(select(User).where(User.email == body.email))
    if user is None or not user.is_active:
        return answer
    settings = get_settings()
    token = create_password_reset_token(user.id, user.password_hash)
    link = f"{settings.frontend_url.rstrip('/')}/reset-password?token={token}"
    try:
        await send_email(
            user.email,
            "تغییر رمز عبور «جواب»",
            "سلام،\n\nبرای انتخاب رمز عبور تازه روی این لینک بزنید:\n"
            f"{link}\n\n"
            f"این لینک {settings.password_reset_minutes} دقیقه و فقط یک بار کار می‌کند. "
            "اگر شما درخواست نداده‌اید، این ایمیل را نادیده بگیرید.\n\n«جواب»",
        )
    except Exception:
        logger.exception("could not send password reset email")
    return answer


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(body: ResetPasswordRequest, db: DbSession) -> None:
    invalid = HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "لینک تغییر رمز نامعتبر است یا منقضی شده. دوباره درخواست بدهید.",
    )
    try:
        user_id, fingerprint = read_password_reset_token(body.token)
    except TokenError:
        raise invalid from None
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise invalid
    if not reset_token_matches(fingerprint, user.password_hash):
        raise invalid  # already used: the password changed since the link was made
    user.password_hash = hash_password(body.new_password)
    await db.commit()
