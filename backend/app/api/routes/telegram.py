"""The panel's Telegram and Bale pages. They are separate channels: each has its own switch,
shop link, linked owner accounts and own bot. Telegram also has Business and channels.

Both messengers share one Bot API (Bale copies Telegram's), so the endpoints are built from
the same helpers with a `platform`.
"""

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
    Shop,
    TelegramAdmin,
    TelegramBot,
    TelegramBusinessConnection,
    TelegramChannel,
)
from app.services import telegram_setup
from app.services.channels import PLANS_FOR_BUSINESS, PLANS_FOR_CUSTOM_BOT
from app.services.notify import shared_bot
from app.services.telegram import TelegramClient
from app.services.telegram_bot import LINK_CODE_LIFETIME
from app.services.telegram_setup import BotSetupError, bot_link

router = APIRouter(prefix="/telegram", tags=["telegram"])
bale_router = APIRouter(prefix="/bale", tags=["bale"])

_APP_NAMES = {"telegram": "تلگرام", "bale": "بله"}


class AdminOut(BaseModel):
    id: uuid.UUID
    telegram_user_id: int
    username: str | None
    first_name: str
    notify: bool


class CustomBotOut(BaseModel):
    username: str
    active: bool
    # Persian, when the messenger rejected the token or webhook.
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


class MessengerStatus(BaseModel):
    """What Telegram and Bale have in common."""

    # False until the server runs the shared bot (TELEGRAM_BOT_TOKEN / BALE_BOT_TOKEN).
    available: bool
    # The shop's switch for answering on this messenger.
    enabled: bool
    shared_bot_username: str | None
    # The shop's start link on the shared bot: put it in the Instagram bio, the channel...
    shop_link: str | None
    # Customers can also send this code to the bot if a start link doesn't carry it.
    shop_code: str
    # Accounts on this messenger linked to the shop (alerts + managing from the bot).
    admins: list[AdminOut]
    custom_bot: CustomBotOut | None
    custom_bot_allowed: bool
    plan: Plan


class TelegramStatus(MessengerStatus):
    business: BusinessOut
    business_allowed: bool
    # The bot the owner adds in Telegram > Settings > Telegram Business > Chatbots.
    business_bot_username: str | None
    channels: list[ChannelOut]


class BaleStatus(MessengerStatus):
    pass


class MessengerUpdate(BaseModel):
    enabled: bool


class LinkOut(BaseModel):
    # Open this in the messenger (on the owner's phone) to link the account.
    url: str
    expires_at: datetime


class CustomBotIn(BaseModel):
    token: str = Field(min_length=10, max_length=200, pattern=r"^\d+:[\w-]+$")


# ---------------------------------------------------------------------------- shared helpers


async def _custom_bot(db: DbSession, shop: Shop, platform: str) -> TelegramBot | None:
    return await db.scalar(
        select(TelegramBot).where(TelegramBot.shop_id == shop.id, TelegramBot.platform == platform)
    )


async def _common(db: DbSession, shop: Shop, platform: str) -> dict:
    shared = await shared_bot(db, platform)
    custom = await _custom_bot(db, shop, platform)
    admins = (
        await db.scalars(
            select(TelegramAdmin).where(
                TelegramAdmin.shop_id == shop.id, TelegramAdmin.platform == platform
            )
        )
    ).all()
    return {
        "available": shared is not None,
        "enabled": shop.channel_enabled(platform),
        "shared_bot_username": shared.username if shared else None,
        "shop_link": f"{bot_link(platform, shared.username)}?start=s_{shop.slug}"
        if shared
        else None,
        "shop_code": shop.slug,
        "admins": [
            AdminOut(
                id=a.id,
                telegram_user_id=a.telegram_user_id,
                username=a.username,
                first_name=a.first_name,
                notify=a.notify,
            )
            for a in admins
        ],
        "custom_bot": (
            CustomBotOut(
                username=custom.username,
                active=custom.is_active,
                last_error=custom.last_error,
                link=bot_link(platform, custom.username),
            )
            if custom is not None
            else None
        ),
        "custom_bot_allowed": shop.plan in PLANS_FOR_CUSTOM_BOT,
        "plan": shop.plan,
    }


async def _set_enabled(db: DbSession, shop: Shop, platform: str, enabled: bool) -> None:
    if platform == "bale":
        shop.bale_enabled = enabled
    else:
        shop.telegram_enabled = enabled
    await db.commit()


async def _create_link(db: DbSession, shop: Shop, platform: str) -> LinkOut:
    """A one-time link that connects the owner's account on this messenger to the shop."""
    shared = await shared_bot(db, platform)
    if shared is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"ربات {_APP_NAMES[platform]} هنوز فعال نشده است.",
        )
    shop.telegram_link_code = secrets.token_urlsafe(18)
    shop.telegram_link_expires_at = utcnow() + LINK_CODE_LIFETIME
    await db.commit()
    return LinkOut(
        url=f"{bot_link(platform, shared.username)}?start=a_{shop.telegram_link_code}",
        expires_at=shop.telegram_link_expires_at,
    )


async def _remove_admin(db: DbSession, shop: Shop, platform: str, admin_id: uuid.UUID) -> None:
    admin = await db.get(TelegramAdmin, admin_id)
    if admin is None or admin.shop_id != shop.id or admin.platform != platform:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیدا نشد")
    await db.delete(admin)
    await db.commit()


async def _connect_bot(
    db: DbSession, shop: Shop, platform: str, token: str, client: TelegramClient
) -> None:
    try:
        await telegram_setup.connect_custom_bot(db, shop, token, client, platform=platform)
    except BotSetupError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None


# ---------------------------------------------------------------------------- Telegram


async def _telegram_status(db: DbSession, shop: Shop) -> TelegramStatus:
    common = await _common(db, shop, "telegram")
    connection = await db.scalar(
        select(TelegramBusinessConnection)
        .where(TelegramBusinessConnection.shop_id == shop.id)
        .order_by(TelegramBusinessConnection.updated_at.desc())
    )
    channels = (
        await db.scalars(select(TelegramChannel).where(TelegramChannel.shop_id == shop.id))
    ).all()
    custom = await _custom_bot(db, shop, "telegram")
    business_bot = (
        custom.username
        if custom is not None and custom.is_active
        else common["shared_bot_username"]
    )
    return TelegramStatus(
        **common,
        business=BusinessOut(
            connected=connection is not None,
            enabled=bool(connection and connection.is_enabled),
            can_reply=bool(connection and connection.can_reply),
            telegram_user_id=connection.telegram_user_id if connection else None,
        ),
        business_allowed=shop.plan in PLANS_FOR_BUSINESS,
        business_bot_username=business_bot,
        channels=[
            ChannelOut(id=c.id, title=c.title, username=c.username, active=c.is_active)
            for c in channels
        ],
    )


@router.get("", response_model=TelegramStatus)
async def get_status(shop: CurrentShop, db: DbSession) -> TelegramStatus:
    return await _telegram_status(db, shop)


@router.patch("", response_model=TelegramStatus)
async def update(body: MessengerUpdate, shop: CurrentShop, db: DbSession) -> TelegramStatus:
    await _set_enabled(db, shop, "telegram", body.enabled)
    return await _telegram_status(db, shop)


@router.post("/link", response_model=LinkOut)
async def create_link(shop: CurrentShop, db: DbSession) -> LinkOut:
    """A one-time link that connects the owner's Telegram account to this shop."""
    return await _create_link(db, shop, "telegram")


@router.delete("/admins/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_admin(admin_id: uuid.UUID, shop: CurrentShop, db: DbSession) -> None:
    await _remove_admin(db, shop, "telegram", admin_id)


@router.put("/custom-bot", response_model=TelegramStatus)
async def set_custom_bot(
    body: CustomBotIn, shop: CurrentShop, db: DbSession, telegram: Telegram
) -> TelegramStatus:
    """Connect the shop's own Telegram bot by the token @BotFather gave (pro and business)."""
    await _connect_bot(db, shop, "telegram", body.token, telegram)
    return await _telegram_status(db, shop)


@router.delete("/custom-bot", status_code=status.HTTP_204_NO_CONTENT)
async def remove_custom_bot(shop: CurrentShop, db: DbSession, telegram: Telegram) -> None:
    await telegram_setup.disconnect_custom_bot(db, shop, telegram, "telegram")


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


# ---------------------------------------------------------------------------- Bale


async def _bale_status(db: DbSession, shop: Shop) -> BaleStatus:
    return BaleStatus(**await _common(db, shop, "bale"))


@bale_router.get("", response_model=BaleStatus)
async def get_bale(shop: CurrentShop, db: DbSession) -> BaleStatus:
    return await _bale_status(db, shop)


@bale_router.patch("", response_model=BaleStatus)
async def update_bale(body: MessengerUpdate, shop: CurrentShop, db: DbSession) -> BaleStatus:
    await _set_enabled(db, shop, "bale", body.enabled)
    return await _bale_status(db, shop)


@bale_router.post("/link", response_model=LinkOut)
async def create_bale_link(shop: CurrentShop, db: DbSession) -> LinkOut:
    """A one-time link that connects the owner's Bale account to this shop."""
    return await _create_link(db, shop, "bale")


@bale_router.delete("/admins/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_bale_admin(admin_id: uuid.UUID, shop: CurrentShop, db: DbSession) -> None:
    await _remove_admin(db, shop, "bale", admin_id)


@bale_router.put("/custom-bot", response_model=BaleStatus)
async def set_bale_custom_bot(
    body: CustomBotIn, shop: CurrentShop, db: DbSession, telegram: Telegram
) -> BaleStatus:
    """Connect the shop's own Bale bot by the token Bale's @botfather gave (pro and business)."""
    await _connect_bot(db, shop, "bale", body.token, telegram)
    return await _bale_status(db, shop)


@bale_router.delete("/custom-bot", status_code=status.HTTP_204_NO_CONTENT)
async def remove_bale_custom_bot(shop: CurrentShop, db: DbSession, telegram: Telegram) -> None:
    await telegram_setup.disconnect_custom_bot(db, shop, telegram, "bale")
