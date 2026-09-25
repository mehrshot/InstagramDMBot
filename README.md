# جواب (Javab)

**هیچ دایرکتی بی‌جواب نمی‌مونه.** دستیار هوش مصنوعی فروشگاه‌های اینستاگرامی: با اطلاعات و محصولات هر فروشگاه به دایرکت‌ها جواب می‌دهد و هر جا لازم باشد گفتگو را به صاحب پیج می‌سپارد.

- `backend/`: پایتون (FastAPI)
- `frontend/`: پنل فروشگاه (React + TypeScript)

- **راهنمای کامل فرانت‌اند (برای علی):** [docs/FRONTEND.md](docs/FRONTEND.md)
- **پنل (فرانت‌اند):** [frontend/](frontend/README.md)
- **اسکیمای API:** [docs/openapi.json](docs/openapi.json)
- **برنامه‌ی کانال‌های جدید (واتس‌اپ، تلگرام، بله):** [docs/channels-plan.md](docs/channels-plan.md)
- **راهنمای اجرایی راه‌اندازی (دامنه، متا، سرور، اولین تست واقعی):** [docs/setup-guide.html](docs/setup-guide.html) — [نسخه‌ی آنلاین](https://claude.ai/artifact/Y8e2fe5JsHpLCkxrBHz8Y1)
- **نقشه‌ی لانچ (کارهای بیرون از کد، قدم‌به‌قدم):** [docs/launch-guide.html](docs/launch-guide.html) — فایل را دانلود و در مرورگر باز کنید، یا [نسخه‌ی آنلاین](https://claude.ai/artifact/MjudMjNEeSQR3Yze5A3BXn)

## اجرای کل پروژه روی کامپیوتر خودتان (بک‌اند + پنل)

پیش‌نیاز: [uv](https://docs.astral.sh/uv/) و [Node.js 20+](https://nodejs.org/). به Docker، Redis، اینستاگرام یا کلید هوش مصنوعی نیاز نیست.

۱. فایل `backend/.env` را مثل بخش «اجرای محلی» پایین بسازید. بعد:

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed_demo
uv run uvicorn app.main:app --reload
```

۲. در یک ترمینال دیگر:

```bash
cd frontend
npm install
npm run dev
```

۳. پنل را در `http://localhost:3000` باز کنید و با `demo@shop.ir` / `demopass123` وارد شوید.

۴. دایرکت مشتری را شبیه‌سازی کنید (باید در بخش «ارجاع‌شده به شما» پنل ظاهر شود):

```bash
cd backend
uv run python -m scripts.simulate dm --text "سلام" --text "فاکتور رسمی میدید؟"
```

### تست هوش مصنوعی واقعی

سه مقدار `LLM_BASE_URL`، `LLM_API_KEY` و `LLM_MODEL` را در `backend/.env` بگذارید (راهنما: قدم ۱.۳ نقشه‌ی لانچ)، بعد:

```bash
cd backend
uv run python -m scripts.check_llm --price-in 0.10 --price-out 0.50
```

سه سناریوی واقعی (سوال محصول، سوال از اطلاعات فروشگاه، سوالی که باید به مدیر ارجاع شود) را اجرا می‌کند و هزینه‌ی هر جواب را تخمین می‌زند.

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
frontend/          پنل فروشگاه (React + TypeScript + Vite) — frontend/README.md
deploy/            Caddyfile (HTTPS خودکار) و web.Dockerfile (ساخت پنل)
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

مقادیر `.env` را پر کنید (راهنمای هر مقدار داخل فایل هست) و رکورد DNS هر دو دامنه‌ی `API_DOMAIN` و `PANEL_DOMAIN` را به IP سرور بزنید، بعد:

```bash
docker compose up -d --build
```

این دستور همه‌چیز را بالا می‌آورد: دیتابیس، Redis، بک‌اند، worker و سرویس `web` (پنل ساخته‌شده از `frontend/` + HTTPS خودکار برای هر دو دامنه با Caddy). Migrationها موقع بالا آمدن `api` خودکار اجرا می‌شوند.

به‌روزرسانی بعد از هر push:

```bash
git pull && docker compose up -d --build
```

راهنمای کامل و قدم‌به‌قدم: [docs/setup-guide.html](docs/setup-guide.html).

## قرارداد API برای فرانت

کامل در [docs/FRONTEND.md](docs/FRONTEND.md).
