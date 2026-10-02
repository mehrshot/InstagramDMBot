"""The panel's Telegram page: the shop's start link, linking the owner's account, the shop's
own bot, the Telegram Business connection and channels."""

import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentShop, DbSession, Telegram
from app.core.timeutil import utcnow
from app.models import (
    Plan,
    TelegramAdmin,
    TelegramBot,
    TelegramBusinessConnection,
    TelegramChannel,
)
from app.services import telegram_setup
from app.services.channels import PLANS_FOR_BUSINESS, PLANS_FOR_CUSTOM_BOT
from app.services.notify import shared_bot
from app.services.telegram_bot import LINK_CODE_LIFETIME
from app.services.telegram_setup import BotSetupError

router = APIRouter(prefix="/telegram", tags=["telegram"])


class AdminOut(BaseModel):
    id: uuid.UUID
    telegram_user_id: int
    username: str | None
    first_name: str
    notify: bool


class CustomBotOut(BaseModel):
    username: str
    active: bool
    # Persian, when Telegram rejected the token or webhook.
    last_error: str | None
    # Customers open this to talk to the shop's own bot.
    link: str


class BusinessOut(BaseModel):
    connected: bool
    enabled: bool
    # False if the owner didn't give the bot the "reply to messages" right in Telegram.
    can_reply: bool
    telegram_user_id: int | None


class ChannelOut(BaseModel):
    id: uuid.UUID
    title: str
    username: str | None
    active: bool


class TelegramStatus(BaseModel):
    # False until the server has the shared bot (TELEGRAM_BOT_TOKEN).
    available: bool
    # The shop's switch for all Telegram answering.
    enabled: bool
    shared_bot_username: str | None
    # The shop's start link on the shared bot: put it in the Instagram bio, the channel...
    shop_link: str | None
    # Accounts linked to the shop (alerts + managing from the bot).
    admins: list[AdminOut]
    custom_bot: CustomBotOut | None
    custom_bot_allowed: bool
    business: BusinessOut
    business_allowed: bool
    # The bot the owner adds in Telegram > Settings > Telegram Business > Chatbots.
    business_bot_username: str | None
    channels: list[ChannelOut]
    plan: Plan


class TelegramUpdate(BaseModel):
    enabled: bool


class LinkOut(BaseModel):
    # Open this in Telegram (on the owner's phone) to link the account.
    url: str
    expires_at: datetime


class CustomBotIn(BaseModel):
    token: str = Field(min_length=10, max_length=200, pattern=r"^\d+:[\w-]+$")


@router.get("", response_model=TelegramStatus)
async def get_status(shop: CurrentShop, db: DbSession) -> TelegramStatus:
    shared = await shared_bot(db)
    custom = await db.scalar(select(TelegramBot).where(TelegramBot.shop_id == shop.id))
    connection = await db.scalar(
        select(TelegramBusinessConnection)
        .where(TelegramBusinessConnection.shop_id == shop.id)
        .order_by(TelegramBusinessConnection.updated_at.desc())
    )
    admins = (await db.scalars(select(TelegramAdmin).where(TelegramAdmin.shop_id == shop.id))).all()
    channels = (
        await db.scalars(select(TelegramChannel).where(TelegramChannel.shop_id == shop.id))
    ).all()
    business_bot = custom if custom is not None and custom.is_active else shared
    return TelegramStatus(
        available=shared is not None,
        enabled=shop.telegram_enabled,
        shared_bot_username=shared.username if shared else None,
        shop_link=f"https://t.me/{shared.username}?start=s_{shop.slug}" if shared else None,
        admins=[
            AdminOut(
                id=a.id,
                telegram_user_id=a.telegram_user_id,
                username=a.username,
                first_name=a.first_name,
                notify=a.notify,
            )
            for a in admins
        ],
        custom_bot=(
            CustomBotOut(
                username=custom.username,
                active=custom.is_active,
                last_error=custom.last_error,
                link=f"https://t.me/{custom.username}",
            )
            if custom is not None
            else None
        ),
        custom_bot_allowed=shop.plan in PLANS_FOR_CUSTOM_BOT,
        business=BusinessOut(
            connected=connection is not None,
            enabled=bool(connection and connection.is_enabled),
            can_reply=bool(connection and connection.can_reply),
            telegram_user_id=connection.telegram_user_id if connection else None,
        ),
        business_allowed=shop.plan in PLANS_FOR_BUSINESS,
        business_bot_username=business_bot.username if business_bot else None,
        channels=[
            ChannelOut(id=c.id, title=c.title, username=c.username, active=c.is_active)
            for c in channels
        ],
        plan=shop.plan,
    )


@router.patch("", response_model=TelegramStatus)
async def update(body: TelegramUpdate, shop: CurrentShop, db: DbSession) -> TelegramStatus:
    shop.telegram_enabled = body.enabled
    await db.commit()
    return await get_status(shop, db)


@router.post("/link", response_model=LinkOut)
async def create_link(shop: CurrentShop, db: DbSession) -> LinkOut:
    """A one-time link that connects the owner's Telegram account to this shop."""
    shared = await shared_bot(db)
    if shared is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ربات تلگرام هنوز فعال نشده است.")
    shop.telegram_link_code = secrets.token_urlsafe(18)
    shop.telegram_link_expires_at = utcnow() + LINK_CODE_LIFETIME
    await db.commit()
    return LinkOut(
        url=f"https://t.me/{shared.username}?start=a_{shop.telegram_link_code}",
        expires_at=shop.telegram_link_expires_at,
    )


@router.delete("/admins/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_admin(admin_id: uuid.UUID, shop: CurrentShop, db: DbSession) -> None:
    admin = await db.get(TelegramAdmin, admin_id)
    if admin is None or admin.shop_id != shop.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیدا نشد")
    await db.delete(admin)
    await db.commit()


@router.put("/custom-bot", response_model=TelegramStatus)
async def set_custom_bot(
    body: CustomBotIn, shop: CurrentShop, db: DbSession, telegram: Telegram
) -> TelegramStatus:
    """Connect the shop's own bot by the token @BotFather gave (pro and business plans)."""
    try:
        await telegram_setup.connect_custom_bot(db, shop, body.token, telegram)
    except BotSetupError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return await get_status(shop, db)


@router.delete("/custom-bot", status_code=status.HTTP_204_NO_CONTENT)
async def remove_custom_bot(shop: CurrentShop, db: DbSession, telegram: Telegram) -> None:
    await telegram_setup.disconnect_custom_bot(db, shop, telegram)


@router.delete("/business", status_code=status.HTTP_204_NO_CONTENT)
async def disable_business(shop: CurrentShop, db: DbSession) -> None:
    """Stop answering in the owner's account. (To remove it fully, the owner also removes the
    bot in Telegram > Settings > Telegram Business > Chatbots.)"""
    connections = await db.scalars(
        select(TelegramBusinessConnection).where(TelegramBusinessConnection.shop_id == shop.id)
    )
    for connection in connections:
        connection.is_enabled = False
    await db.commit()


@router.delete("/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_channel(channel_id: uuid.UUID, shop: CurrentShop, db: DbSession) -> None:
    channel = await db.get(TelegramChannel, channel_id)
    if channel is None or channel.shop_id != shop.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیدا نشد")
    channel.is_active = False
    await db.commit()
