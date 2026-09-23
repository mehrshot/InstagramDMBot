from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.queue import Queue
from app.core.security import TokenError, decode_token
from app.models import Shop, User
from app.services.instagram import InstagramClient
from app.services.llm import LLMClient

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="احراز هویت نامعتبر است",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        user_id = decode_token(credentials.credentials, "access")
    except TokenError:
        raise unauthorized from None

    user = await db.scalar(select(User).where(User.id == user_id).options(selectinload(User.shop)))
    if user is None or not user.is_active:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_shop(user: CurrentUser) -> Shop:
    return user.shop


CurrentShop = Annotated[Shop, Depends(get_current_shop)]


def get_queue(request: Request) -> Queue:
    return request.app.state.queue


def get_instagram_client(request: Request) -> InstagramClient:
    return InstagramClient(request.app.state.http)


JobQueue = Annotated[Queue, Depends(get_queue)]
Instagram = Annotated[InstagramClient, Depends(get_instagram_client)]


def get_http(request: Request) -> httpx.AsyncClient:
    return request.app.state.http


HttpClient = Annotated[httpx.AsyncClient, Depends(get_http)]


def get_llm(http: HttpClient) -> LLMClient:
    return LLMClient(http)


LLM = Annotated[LLMClient, Depends(get_llm)]
