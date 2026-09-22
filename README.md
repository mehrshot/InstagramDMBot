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
    services/    منطق اصلی: اینستاگرام، webhook، پایپ‌لاین پیام‌ها، تولید جواب
    worker.py    پردازش پس‌زمینه (arq + Redis)
  alembic/       migrationهای دیتابیس
  scripts/       ابزارهای توسعه (شبیه‌ساز دایرکت)
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
QUEUE_BACKEND=inline
INSTAGRAM_DRY_RUN=true
META_APP_SECRET=local-secret
```

- `QUEUE_BACKEND=inline`: کارهای پس‌زمینه داخل خود سرور اجرا می‌شوند و Redis لازم نیست (فقط برای توسعه).
- `INSTAGRAM_DRY_RUN=true`: جواب ربات به جای ارسال به اینستاگرام در لاگ سرور چاپ می‌شود.
- روی ویندوز اگر متن فارسی در لاگ به شکل `\u0633...` دیده شد، قبل از اجرای سرور متغیر محیطی `PYTHONUTF8=1` را در ترمینال تنظیم کنید.

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

### شبیه‌سازی دایرکت بدون متا

تا وقتی اپ متا آماده نشده، این اسکریپت نقش اینستاگرام را بازی می‌کند. اول در `/docs` یک کاربر ثبت‌نام کنید، بعد:

```bash
uv run python -m scripts.simulate link --email owner@shop.ir
```

```bash
uv run python -m scripts.simulate dm --text "سلام" --text "این مانتو" --text "سایز ۴۴ داره؟"
```

```bash
uv run python -m scripts.simulate dm --echo --text "بله عزیزم موجوده"
```

دستور اول یک پیج اینستاگرام ساختگی به فروشگاه وصل و ربات را روشن می‌کند. دومی سه پیام پشت‌سرهم از طرف مشتری می‌فرستد (ربات فقط **یک** جواب می‌دهد). سومی یعنی صاحب پیج خودش جواب داده و ربات برای آن مشتری ساکت می‌شود.

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
| GET | `/instagram` | وضعیت اتصال: `{connected, active, username, ig_user_id, token_expires_at}` |
| GET | `/instagram/connect-url` | `{url}`: مرورگر کاربر را به این آدرس بفرستید |
| DELETE | `/instagram` | قطع اتصال پیج |

### اتصال اینستاگرام از سمت فرانت

1. کاربر روی «اتصال اینستاگرام» می‌زند. فرانت `GET /instagram/connect-url` را صدا می‌زند و `window.location = url`.
2. کاربر در صفحه‌ی اینستاگرام اجازه می‌دهد. اینستاگرام او را به بک‌اند برمی‌گرداند و بک‌اند اتصال را کامل می‌کند.
3. بک‌اند مرورگر را به **`{FRONTEND_URL}/instagram/callback`** می‌فرستد. این صفحه را علی باید بسازد و پارامترهایش این‌هاست:

| `status` | `reason` | پیامی که به کاربر نشان داده شود |
|---|---|---|
| `connected` | - | پیج با موفقیت وصل شد |
| `denied` | - | اجازه‌ی دسترسی داده نشد |
| `error` | `account_in_use` | این پیج به حساب دیگری وصل است |
| `error` | `invalid_state` | لینک منقضی شده، دوباره تلاش کنید |
| `error` | `instagram` / `missing_code` | خطا در ارتباط با اینستاگرام، دوباره تلاش کنید |

اگر `active` در `GET /instagram` برابر `false` باشد، یعنی اینستاگرام دسترسی را لغو کرده (مثلاً رمز پیج عوض شده) و کاربر باید دوباره وصل کند. این حالت را با یک هشدار واضح در پنل نشان دهید.

### نکات کلی

- عمر access token ۳۰ دقیقه و refresh token ۳۰ روز است. روی پاسخ 401، فرانت یک بار `/auth/refresh` را صدا بزند.
- خطاها به شکل `{"detail": "..."}` با متن فارسی برمی‌گردند. خطای اعتبارسنجی (422) لیستی از فیلدهای مشکل‌دار است.
