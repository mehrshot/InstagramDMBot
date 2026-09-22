# DM Assistant — دستیار هوشمند دایرکت اینستاگرام

بک‌اند پایتون (FastAPI) برای رباتی که با اطلاعات هر فروشگاه به دایرکت‌های اینستاگرام جواب می‌دهد.

## ساختار

```
backend/
  app/
    core/        تنظیمات، دیتابیس، امنیت (JWT، هش رمز، رمزنگاری توکن‌ها)
    models/      جداول دیتابیس
    schemas/     مدل‌های ورودی/خروجی API
    api/routes/  endpointها
    worker.py    پردازش پس‌زمینه (arq + Redis)
  alembic/       migrationهای دیتابیس
  tests/
deploy/Caddyfile   HTTPS خودکار
docker-compose.yml
```

## اجرای محلی (بدون Docker)

پیش‌نیاز: [uv](https://docs.astral.sh/uv/)

```bash
cd backend
uv sync
```

برای توسعه‌ی محلی می‌شود به جای Postgres از SQLite استفاده کرد. یک فایل `backend/.env` بسازید:

```
DATABASE_URL=sqlite+aiosqlite:///./dev.db
ENCRYPTION_KEY=<خروجی دستور زیر>
```

```bash
uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

```bash
uv run alembic upgrade head
```

```bash
uv run uvicorn app.main:app --reload
```

مستندات تعاملی API (برای علی): http://localhost:8000/docs

## تست

```bash
uv run pytest
```

## دیپلوی روی سرور

```bash
cp .env.example .env
```

مقادیر `.env` را پر کنید (راهنمای هر مقدار داخل فایل هست) و رکورد DNS دامنه‌ی `API_DOMAIN` را به IP سرور بزنید، بعد:

```bash
docker compose up -d --build
```

Migrationها موقع بالا آمدن سرویس `api` خودکار اجرا می‌شوند.

## قرارداد API برای فرانت

همه‌ی مسیرها زیر `/api/v1` هستند. توکن در هدر `Authorization: Bearer <access_token>`.

| متد | مسیر | توضیح |
|---|---|---|
| POST | `/auth/register` | `{email, password, full_name?, shop_name}` → `{access_token, refresh_token}` |
| POST | `/auth/login` | `{email, password}` → توکن‌ها |
| POST | `/auth/refresh` | `{refresh_token}` → توکن‌های جدید |
| GET | `/me` | کاربر + فروشگاه |
| GET | `/shop` | تنظیمات ربات |
| PATCH | `/shop` | تغییر تنظیمات: `name, bot_enabled, tone (friendly/formal), use_emoji, fallback_message, forbidden_rules, handoff_pause_minutes` |

- عمر access token ۳۰ دقیقه و refresh token ۳۰ روز است. روی پاسخ 401، فرانت یک بار `/auth/refresh` را صدا بزند.
- خطاها به شکل `{"detail": "..."}` با متن فارسی برمی‌گردند. خطای اعتبارسنجی (422) لیستی از فیلدهای مشکل‌دار است.
