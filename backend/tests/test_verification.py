"""Email and phone verification, the sign-up gift, and the login rate limit."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.timeutil import utcnow
from app.models import GiftClaim, Shop, TelegramBot, User, WalletEntry, WalletEntryKind
from app.services import phone
from tests.conftest import FakeWeb, RecordingQueue
from tests.test_telegram import OWNER, _link_owner, _private, _update, setup  # noqa: F401

REGISTER = {"email": "new@shop.ir", "password": "strongpass1", "shop_name": "S"}


def _contact(user_id: int, number: str, sender: int = OWNER) -> dict:
    update = _private(sender, contact={"phone_number": number, "user_id": user_id})
    return update


def _keyboard_rows(fake_web: FakeWeb) -> list:
    for message in reversed(fake_web.telegram.sent()):
        markup = message.get("reply_markup") or {}
        if "keyboard" in markup:
            return markup["keyboard"]
    return []


def _asks_for_phone(fake_web: FakeWeb) -> bool:
    return any(b.get("request_contact") for row in _keyboard_rows(fake_web) for b in row)


async def _gifts(db: AsyncSession, shop: Shop) -> list[WalletEntry]:
    return list(
        (
            await db.scalars(
                select(WalletEntry).where(
                    WalletEntry.shop_id == shop.id, WalletEntry.kind == WalletEntryKind.BONUS
                )
            )
        ).all()
    )


# ---------------------------------------------------------------------------- the gift


async def test_gift_after_linking_and_sharing_the_phone(
    db: AsyncSession,
    setup: tuple[Shop, TelegramBot],  # noqa: F811
    fake_web: FakeWeb,
    queue: RecordingQueue,
    billing_on: None,
) -> None:
    shop, bot = setup
    await _link_owner(db, shop, bot, fake_web, queue)
    assert await _gifts(db, shop) == []  # linked, but the number isn't verified yet
    assert "تأیید شماره" in fake_web.telegram.sent()[-1]["text"]
    assert _asks_for_phone(fake_web)

    await _update(db, bot, fake_web, queue, _contact(OWNER, "989121234567"))
    owner = await db.scalar(select(User))
    assert owner is not None and owner.phone == "+989121234567"
    assert owner.phone_verified_at is not None
    credit = get_settings().signup_credit_rial
    assert [g.amount_rial for g in await _gifts(db, shop)] == [credit]
    await db.refresh(shop)
    assert shop.balance_rial == credit and shop.signup_gift_at is not None
    assert "هدیه" in fake_web.telegram.sent()[-1]["text"]
    assert not _asks_for_phone(fake_web)

    # Sharing again changes nothing.
    await _update(db, bot, fake_web, queue, _contact(OWNER, "989121234567"))
    assert len(await _gifts(db, shop)) == 1


async def test_only_your_own_contact_counts(
    db: AsyncSession,
    setup: tuple[Shop, TelegramBot],  # noqa: F811
    fake_web: FakeWeb,
    queue: RecordingQueue,
    billing_on: None,
) -> None:
    shop, bot = setup
    await _link_owner(db, shop, bot, fake_web, queue)
    await _update(db, bot, fake_web, queue, _contact(9999, "989121234567"))
    owner = await db.scalar(select(User))
    assert owner is not None and owner.phone is None
    assert await _gifts(db, shop) == []


async def test_one_gift_per_messenger_account(
    db: AsyncSession,
    setup: tuple[Shop, TelegramBot],  # noqa: F811
    fake_web: FakeWeb,
    queue: RecordingQueue,
    billing_on: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Moving the same Telegram account to a new shop (or a deleted-and-new one) pays nothing."""
    monkeypatch.setattr(get_settings(), "signup_gift_requires_phone", False)
    shop, bot = setup
    await _link_owner(db, shop, bot, fake_web, queue)
    assert len(await _gifts(db, shop)) == 1  # no phone needed on this server

    second = User(email="second@shop.ir", password_hash="x")
    second.shop = Shop(name="دوم", slug="second12")
    db.add(second)
    await db.commit()
    second.shop.telegram_link_code = "SECONDCODE1"
    second.shop.telegram_link_expires_at = utcnow() + timedelta(minutes=5)
    await db.commit()
    await _update(db, bot, fake_web, queue, _private(OWNER, "/start a_SECONDCODE1"))
    assert await _gifts(db, second.shop) == []
    # Stored as hashes only: no Telegram id or number in the table.
    keys = (await db.scalars(select(GiftClaim.key))).all()
    assert keys and all(str(OWNER) not in k for k in keys)


async def test_a_number_belongs_to_one_account(
    db: AsyncSession,
    setup: tuple[Shop, TelegramBot],  # noqa: F811
    fake_web: FakeWeb,
    queue: RecordingQueue,
    billing_on: None,
) -> None:
    shop, bot = setup
    other = User(email="other@shop.ir", password_hash="x", phone="+989121234567")
    other.phone_verified_at = utcnow()
    other.shop = Shop(name="دیگر", slug="other123")
    db.add(other)
    await db.commit()
    await _link_owner(db, shop, bot, fake_web, queue)
    await _update(db, bot, fake_web, queue, _contact(OWNER, "+98 912 123 4567"))
    assert "حساب دیگری" in fake_web.telegram.sent()[-1]["text"]
    assert await _gifts(db, shop) == []


# ---------------------------------------------------------------------------- phone by SMS


@pytest.fixture
def sms(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    sent: list[tuple[str, str]] = []

    async def fake_send(http, number: str, code: str) -> None:  # type: ignore[no-untyped-def]
        sent.append((number, code))

    monkeypatch.setattr(phone, "send_code", fake_send)
    return sent


async def _register(client: AsyncClient, **extra: str) -> dict[str, str]:
    resp = await client.post("/api/v1/auth/register", json={**REGISTER, **extra})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def test_phone_verification_by_sms(
    client: AsyncClient, sms: list[tuple[str, str]], billing_on: None
) -> None:
    headers = await _register(client)
    resp = await client.post("/api/v1/me/phone", json={"phone": "۰۹۱۲ ۱۲۳ ۴۵۶۷"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["phone"] == "09121234567"
    assert sms[0][0] == "+989121234567"
    code = sms[0][1]

    wrong = "000000" if code != "000000" else "111111"
    resp = await client.post("/api/v1/me/phone/verify", json={"code": wrong}, headers=headers)
    assert resp.status_code == 400
    resp = await client.post("/api/v1/me/phone/verify", json={"code": code}, headers=headers)
    assert resp.status_code == 200, resp.text
    # Verified, but no gift: no Telegram/Bale account is linked yet.
    assert resp.json() == {"phone": "09121234567", "gift_toman": 0}
    me = (await client.get("/api/v1/me", headers=headers)).json()
    assert me["phone"] == "+989121234567" and me["phone_verified_at"]

    # A second code within the minute is refused.
    resp = await client.post("/api/v1/me/phone", json={"phone": "09121234568"}, headers=headers)
    assert resp.status_code == 429


async def test_phone_codes_are_checked(
    client: AsyncClient, sms: list[tuple[str, str]], db: AsyncSession
) -> None:
    headers = await _register(client)
    resp = await client.post("/api/v1/me/phone", json={"phone": "12345"}, headers=headers)
    assert resp.status_code == 400  # not a mobile number

    await client.post("/api/v1/me/phone", json={"phone": "09121234567"}, headers=headers)
    for _ in range(phone.MAX_CODE_ATTEMPTS):
        await client.post("/api/v1/me/phone/verify", json={"code": "999999x"}, headers=headers)
    resp = await client.post("/api/v1/me/phone/verify", json={"code": sms[0][1]}, headers=headers)
    assert resp.status_code == 400  # too many wrong tries: ask for a new code

    other = await _register(client, email="other@shop.ir")
    user = await db.scalar(select(User).where(User.email == "new@shop.ir"))
    assert user is not None
    user.phone, user.phone_verified_at = "+989121234567", utcnow()
    await db.commit()
    resp = await client.post("/api/v1/me/phone", json={"phone": "09121234567"}, headers=other)
    assert resp.status_code == 400 and "حساب دیگری" in resp.json()["detail"]


def test_normalizing_numbers() -> None:
    assert phone.normalize_iran_mobile("+98 912-123-4567") == "+989121234567"
    assert phone.normalize_iran_mobile("00989121234567") == "+989121234567"
    assert phone.normalize_iran_mobile("9121234567") == "+989121234567"
    with pytest.raises(phone.PhoneError):
        phone.normalize_iran_mobile("02112345678")  # a landline
    assert phone.normalize_contact_phone("989121234567") == "+989121234567"
    assert phone.normalize_contact_phone("+44 7700 900123") == "+447700900123"
    assert phone.local_format("+989121234567") == "09121234567"


# ---------------------------------------------------------------------------- email


async def test_email_verification(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.routes import auth

    mails: list[tuple[str, str]] = []

    async def fake_send(to: str, subject: str, body: str, html_body: str | None = None) -> None:
        mails.append((to, body))

    monkeypatch.setattr(auth, "send_email", fake_send)
    headers = await _register(client)
    assert mails and mails[0][0] == "new@shop.ir"
    token = mails[0][1].split("token=")[1].split()[0]
    me = (await client.get("/api/v1/me", headers=headers)).json()
    assert me["email_verified_at"] is None

    bad = await client.post("/api/v1/auth/email/verify", json={"token": token[:-3] + "abc"})
    assert bad.status_code == 400
    resp = await client.post("/api/v1/auth/email/verify", json={"token": token})
    assert resp.status_code == 204
    me = (await client.get("/api/v1/me", headers=headers)).json()
    assert me["email_verified_at"] is not None
    resp = await client.post("/api/v1/auth/email/resend", headers=headers)
    assert "قبلا تأیید" in resp.json()["message"]


async def test_resending_the_verification_email_is_limited(client: AsyncClient) -> None:
    headers = await _register(client)
    assert (await client.post("/api/v1/auth/email/resend", headers=headers)).status_code == 202
    assert (await client.post("/api/v1/auth/email/resend", headers=headers)).status_code == 429


# ---------------------------------------------------------------------------- login


async def test_wrong_passwords_lock_the_login_for_a_while(client: AsyncClient) -> None:
    await _register(client)
    wrong = {"email": REGISTER["email"], "password": "wrongpass1"}
    for _ in range(get_settings().login_max_failures):
        assert (await client.post("/api/v1/auth/login", json=wrong)).status_code == 401
    right = {"email": REGISTER["email"], "password": REGISTER["password"]}
    resp = await client.post("/api/v1/auth/login", json=right)
    assert resp.status_code == 429 and "دقیقه" in resp.json()["detail"]
    # Another account from elsewhere is unaffected by this email's lock.
    await _register(client, email="b@shop.ir")
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "b@shop.ir", "password": REGISTER["password"]}
    )
    assert resp.status_code == 200


async def test_a_successful_login_clears_the_failures(client: AsyncClient) -> None:
    await _register(client)
    wrong = {"email": REGISTER["email"], "password": "wrongpass1"}
    right = {"email": REGISTER["email"], "password": REGISTER["password"]}
    for _ in range(get_settings().login_max_failures - 1):
        await client.post("/api/v1/auth/login", json=wrong)
    assert (await client.post("/api/v1/auth/login", json=right)).status_code == 200
    for _ in range(get_settings().login_max_failures - 1):
        await client.post("/api/v1/auth/login", json=wrong)
    assert (await client.post("/api/v1/auth/login", json=right)).status_code == 200
