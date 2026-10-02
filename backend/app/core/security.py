import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

# "ig_oauth" is the signed `state` for the Instagram connect flow: it carries the shop id
# through Instagram's redirect and protects the callback against CSRF.
TokenType = Literal["access", "refresh", "ig_oauth"]

_OAUTH_STATE_LIFETIME = timedelta(minutes=15)

_hasher = PasswordHasher()
_ALGORITHM = "HS256"


class TokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_token(subject_id: uuid.UUID, token_type: TokenType) -> str:
    settings = get_settings()
    lifetime = {
        "access": timedelta(minutes=settings.access_token_expire_minutes),
        "refresh": timedelta(days=settings.refresh_token_expire_days),
        "ig_oauth": _OAUTH_STATE_LIFETIME,
    }[token_type]
    now = datetime.now(UTC)
    payload = {"sub": str(subject_id), "type": token_type, "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def decode_token(token: str, expected_type: TokenType) -> uuid.UUID:
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError("invalid token") from exc
    if payload.get("type") != expected_type:
        raise TokenError("wrong token type")
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise TokenError("invalid subject") from exc


def _password_fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def create_password_reset_token(user_id: uuid.UUID, password_hash: str) -> str:
    """A short-lived link token that stops working once the password changes (single use)."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "pwd_reset",
        "fp": _password_fingerprint(password_hash),
        "iat": now,
        "exp": now + timedelta(minutes=settings.password_reset_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


def read_password_reset_token(token: str) -> tuple[uuid.UUID, str]:
    """Returns (user id, password fingerprint); raises TokenError."""
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[_ALGORITHM])
        if payload.get("type") != "pwd_reset":
            raise TokenError("wrong token type")
        return uuid.UUID(payload["sub"]), str(payload["fp"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise TokenError("invalid token") from exc


def reset_token_matches(fingerprint: str, password_hash: str) -> bool:
    return hmac.compare_digest(fingerprint, _password_fingerprint(password_hash))


def _fernet() -> Fernet:
    key = get_settings().encryption_key
    if not key:
        raise RuntimeError("ENCRYPTION_KEY is not configured")
    return Fernet(key.encode())


def encrypt_secret(value: str) -> str:
    """Encrypt third-party credentials (e.g. Instagram access tokens) before storing them."""
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("could not decrypt secret; was ENCRYPTION_KEY changed?") from exc
