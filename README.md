# DM Assistant — دستیار هوشمند دایرکت اینستاگرام

بک‌اند پایتون (FastAPI) برای رباتی که با اطلاعات هر فروشگاه به دایرکت‌های اینستاگرام جواب می‌دهد.

- **راهنمای کامل فرانت‌اند (برای علی):** [docs/FRONTEND.md](docs/FRONTEND.md)
- **اسکیمای API:** [docs/openapi.json](docs/openapi.json)
- **چک‌لیست راه‌اندازی (کارهای بیرون از کد):** [docs/LAUNCH.md](docs/LAUNCH.md)

## ساختار

```
backend/
  app/
    core/        تنظیمات، دیتابیس، امنیت (JWT، هش رمز، رمزنگاری توکن‌ها)
    models/      جداول دیتابیس
    schemas/     مدل‌های ورودی/خروجی API
    api/routes/  endpointها
    services/    منطق اصلی: اینستاگرام، webhook، پیام‌ها، هوش مصنوعی، اطلاعات، محصولات
    worker.py    پردازش پس‌زمینه (arq + Redis)
  alembic/       migrationهای دیتابیس
  scripts/       شبیه‌ساز دایرکت، داده‌ی نمونه، خروجی OpenAPI
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
SECRET_KEY=dev-secret-key-at-least-32-characters-long
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

برای داشتن یک فروشگاه نمونه‌ی پر (ورود با `demo@shop.ir` / `demopass123`):

```bash
uv run python -m scripts.seed_demo
```

برای فعال کردن هوش مصنوعی، این سه مقدار را به `.env` اضافه کنید (هر سرویس سازگار با OpenAI که از tool calling پشتیبانی کند):

```
LLM_BASE_URL=https://...
LLM_API_KEY=...
LLM_MODEL=...
```

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

کامل در [docs/FRONTEND.md](docs/FRONTEND.md).
