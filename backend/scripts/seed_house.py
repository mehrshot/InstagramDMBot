"""Create (or refresh) Javab's own shop: the assistant on the website and in the bot.

    uv run python -m scripts.seed_house --email team@example.com
    uv run python -m scripts.seed_house --email team@example.com --reset-knowledge

The shop belongs to the given account (created with a printed random password if it doesn't
exist), gets the slug SITE_ASSISTANT_SHOP_SLUG and a first version of what Javab is. From then
on the team keeps it up to date like any shop: log in with that account and edit "shop
information", or teach the bot in Telegram. Its prices come live from the server's settings,
so they are not written here. Its conversations (site and bot) show up in that account's inbox,
and questions it can't answer reach the team on Telegram once the account is linked.
"""

import argparse
import asyncio
import secrets
import sys

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.core.timeutil import utcnow
from app.models import KnowledgeEntry, KnowledgeSection, Shop, User

KNOWLEDGE: list[tuple[KnowledgeSection, str, str]] = [
    (
        KnowledgeSection.ABOUT,
        "«جواب» چیست",
        "«جواب» دستیار هوش مصنوعی (ادمین هوشمند) برای فروشگاه‌ها و کسب‌وکارهای آنلاین است. "
        "با اطلاعات و محصولات خود فروشگاه، شبانه‌روز و در چند ثانیه به پیام مشتری‌ها جواب "
        "می‌دهد: قیمت، موجودی، سایز و رنگ، ارسال، پرداخت و سوال‌های همیشگی. چیزی از خودش "
        "نمی‌سازد؛ سوالی را که جوابش در اطلاعات فروشگاه نیست حدس نمی‌زند و به صاحب فروشگاه "
        "می‌سپارد و همان لحظه در تلگرام یا بله‌ی خودش خبرش می‌کند. شعار ما: هیچ پیامی "
        "بی‌جواب نمی‌مونه.\n"
        "کانال‌ها: تلگرام و بله فعال‌اند. اینستاگرام بعد از تأیید رسمی متا اضافه می‌شود. "
        "واتس‌اپ فعلا پشتیبانی نمی‌شود چون شماره‌های ایران را نمی‌پذیرد.",
    ),
    (
        KnowledgeSection.FREE_TEXT,
        "راه‌اندازی در چند دقیقه",
        "۱. در سایت «جواب» حساب بسازید (رایگان).\n"
        "۲. اکانت تلگرام یا بله‌ی خودتان را با لینک یک‌بارمصرفی که پنل می‌سازد وصل کنید.\n"
        "۳. محصولات و اطلاعات فروشگاه را معرفی کنید (روش‌ها پایین آمده).\n"
        "۴. در صفحه‌ی «تست ربات» جای مشتری سوال بپرسید و جواب‌ها را ببینید.\n"
        "۵. ربات را روشن کنید و لینک فروشگاهتان را در بیو اینستاگرام، کانال و استوری بگذارید.\n"
        "معمولا ۱۰ تا ۱۵ دقیقه طول می‌کشد و دانش فنی نمی‌خواهد.",
    ),
    (
        KnowledgeSection.FREE_TEXT,
        "روش‌های کار در تلگرام و بله",
        "- لینک اختصاصی فروشگاه روی ربات «جواب» (پلن پایه): مشتری با زدن لینک مستقیم با "
        "دستیار همان فروشگاه حرف می‌زند.\n"
        "- ربات اختصاصی با اسم و عکس فروشگاه خودتان (پلن حرفه‌ای).\n"
        "- جواب دادن از طرف اکانت شخصی تلگرام خودتان، در همان پی‌وی همیشگی (پلن بیزینس؛ "
        "قابلیت Telegram Business).\n"
        "در بله لینک فروشگاه و ربات اختصاصی هست؛ پست‌های کانال و جواب از اکانت شخصی فقط در "
        "تلگرام است. بله بدون فیلترشکن کار می‌کند.",
    ),
    (
        KnowledgeSection.FREE_TEXT,
        "کامنت، استوری و آمار پیج اینستاگرام",
        "این‌ها همراه اینستاگرام و بعد از تأیید رسمی متا فعال می‌شوند.\n"
        "کامنت‌ها: ربات به کامنت‌های زیر پست و ریلز جواب می‌دهد و از کپشن پست می‌فهمد «قیمتش "
        "چنده؟» درباره‌ی کدام محصول است. خودتان انتخاب می‌کنید: جواب عمومی زیر کامنت، پیام "
        "خصوصی به دایرکت کامنت‌گذار، یا هر دو (جواب کامل در دایرکت و یک خط کوتاه زیر کامنت). "
        "کامنتی را که جوابش را نمی‌داند جواب نمی‌دهد: در پنل، دسته‌بندی‌شده (قیمت، موجودی، "
        "سفارش، شکایت و...) منتظر شما می‌ماند. می‌تواند از تعریف‌ها تشکر کند و اسپم را مخفی "
        "کند. هر کامنتی را می‌شود اول در پنل امتحان کرد.\n"
        "استوری‌ها: عکس یا ویدیوی استوری را آپلود می‌کنید و زمان انتشارش را می‌گذارید؛ «جواب» "
        "سر وقت منتشرش می‌کند. برای هر استوری یک خط می‌نویسید که درباره‌ی چیست، تا وقتی کسی "
        "به استوری جواب داد ربات بفهمد منظورش چیست.\n"
        "آمار پیج: بازدید، تعامل، فالوور و آمار هر پست را می‌خواند و نشان می‌دهد چه چیزی جواب "
        "می‌دهد (نوع پست، بهترین روز و ساعت انتشار، هشتگ‌ها). دستیار محتوای هوش مصنوعی از "
        "روی همین آمار ایده، کپشن و برنامه‌ی هفتگی می‌نویسد و به سوال‌هایی مثل «این هفته چی "
        "پست کنم؟» جواب می‌دهد. جواب کامنت‌ها و دستیار محتوا مثل بقیه‌ی جواب‌ها از کیف پول "
        "کم می‌شوند؛ کامنت‌هایی که جواب نمی‌خواهند هزینه ندارند.",
    ),
    (
        KnowledgeSection.FREE_TEXT,
        "یاد دادن محصولات به ربات",
        "هر جور راحت‌ترید: محصولات را با زبان خودتان برای ربات بنویسید، فایل PDF، Word یا "
        "Excel بفرستید، عکس لیست قیمت یا عکس محصول با توضیح بفرستید، لینک گوگل شیت یا گوگل "
        "داک بدهید، یا پست‌های کانال تلگرامتان را فوروارد کنید. اگر ربات را ادمین کانال کنید، "
        "پست‌های محصول جدید خودکار اضافه می‌شوند. قبل از ثبت، خلاصه‌ی چیزی که فهمیده را نشان "
        "می‌دهد تا تأیید کنید. تغییرها را هم همین‌طور بگویید: «مانتو کتان تموم شد». گوگل شیت "
        "هر چند دقیقه خودکار به‌روز می‌شود. پیام صوتی فعلا پشتیبانی نمی‌شود.",
    ),
    (
        KnowledgeSection.PAYMENT,
        "کیف پول و پرداخت",
        "«جواب» پیش‌پرداخت است: کیف پول فروشگاه را شارژ می‌کنید و هزینه‌ی هر جواب ربات به "
        "اندازه‌ی مصرف از آن کم می‌شود. اشتراک اجباری ندارد؛ پلن‌های بالاتر فقط یک هزینه‌ی "
        "ماهانه‌ی ثابت اضافه دارند. شارژ با درگاه کارت‌به‌کارت «آبان گیت‌وی» است: مبلغ دقیقی "
        "را که صفحه نشان می‌دهد واریز می‌کنید و چند ثانیه بعد کیف پول خودکار شارژ می‌شود. "
        "سوال‌های بی‌ربط مشتری‌ها (مثلا آب‌وهوا) هزینه ندارند. وقتی موجودی تمام شود ربات "
        "پیام‌ها را به خود شما می‌سپارد تا دوباره شارژ کنید. اعتبار شارژشده قابل استرداد نیست.",
    ),
    (
        KnowledgeSection.FAQ,
        "آیا ربات ممکن است اشتباه جواب بدهد؟",
        "فقط از اطلاعات و محصولاتی که خودتان وارد کرده‌اید جواب می‌دهد و چیزی که نمی‌داند را "
        "به شما می‌سپارد. قبل از روشن کردن، در صفحه‌ی تست امتحانش کنید. هر وقت هم خواستید "
        "برای یک مشتری یا کلا خاموشش کنید.",
    ),
    (
        KnowledgeSection.FAQ,
        "ربات سفارش ثبت می‌کند یا پول می‌گیرد؟",
        "نه. «جواب» به سوال‌ها جواب می‌دهد و نحوه‌ی خرید را طبق اطلاعات شما توضیح می‌دهد؛ "
        "سفارش و پرداخت همان روال همیشگی فروشگاه شماست.",
    ),
    (
        KnowledgeSection.FAQ,
        "می‌توانم خودم هم با مشتری‌ها حرف بزنم؟",
        "بله. از پنل یا همان‌جا در تلگرام و بله جواب بدهید؛ ربات در آن گفتگو کنار می‌کشد تا "
        "کار شما تمام شود.",
    ),
    (
        KnowledgeSection.FAQ,
        "داده‌های فروشگاه و مشتری‌ها امن است؟",
        "ارتباط‌ها رمزنگاری‌شده است، رمزها و توکن‌ها رمزنگاری‌شده ذخیره می‌شوند و داده‌ها "
        "فروخته یا برای تبلیغات استفاده نمی‌شوند. با حذف حساب همه‌چیز پاک می‌شود. جزئیات در "
        "صفحه‌ی حریم خصوصی سایت است.",
    ),
    (
        KnowledgeSection.FAQ,
        "اینستاگرام کی اضافه می‌شود؟",
        "به محض تأیید رسمی متا. تا آن موقع می‌توانید لینک تلگرام یا بله‌ی فروشگاه را در بیو "
        "اینستاگرام بگذارید تا مشتری‌ها آنجا جواب بگیرند.",
    ),
    (
        KnowledgeSection.CONTACT,
        "تماس با تیم",
        "همین گفتگو به تیم «جواب» وصل است: اگر جواب سوالی را ندانم، تیم همین‌جا جوابتان را می‌دهد.",
    ),
]

RULES = (
    "درباره‌ی شرکت‌ها و محصولات رقیب نظر نده.\n"
    "تخفیف، قیمت یا امکانی خارج از اطلاعات وعده نده.\n"
    "درباره‌ی جزئیات فنی سرورها، مدل هوش مصنوعی و اعضای تیم حرف نزن.\n"
    "اگر کسی خواست با یک آدم صحبت کند، ارجاع بده."
)


async def main(email: str, reset_knowledge: bool, take_over: bool) -> None:
    slug = get_settings().site_assistant_shop_slug
    if not slug:
        raise SystemExit("SITE_ASSISTANT_SHOP_SLUG is empty")
    email = email.strip().lower()
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        password = None
        if user is None:
            password = secrets.token_urlsafe(12)
            user = User(
                email=email,
                password_hash=hash_password(password),
                full_name="تیم جواب",
                email_verified_at=utcnow(),
            )
            user.shop = Shop(name="جواب", slug=slug)
            db.add(user)
            await db.flush()
        shop = await db.scalar(select(Shop).where(Shop.owner_id == user.id))
        assert shop is not None
        if shop.slug != slug and password is None and not take_over:
            raise SystemExit(
                f"{email} already has the shop {shop.name!r}. Use a separate account for "
                "Javab's own shop, or pass --take-over to turn that shop into it."
            )
        other = await db.scalar(select(Shop).where(Shop.slug == slug, Shop.id != shop.id))
        if other is not None:
            raise SystemExit(f"another shop ({other.name}) already uses the slug {slug!r}")
        shop.slug = slug
        shop.name = "جواب"
        shop.bot_enabled = True
        shop.tone = "friendly"
        shop.use_emoji = True
        shop.fallback_message = "سوالتان را برای تیم «جواب» فرستادم؛ همین‌جا جوابتان را می‌دهیم 🙏"
        shop.forbidden_rules = RULES
        shop.signup_gift_at = shop.signup_gift_at or utcnow()  # no gift for ourselves
        has_knowledge = await db.scalar(
            select(KnowledgeEntry.id).where(KnowledgeEntry.shop_id == shop.id).limit(1)
        )
        if reset_knowledge or has_knowledge is None:
            await db.execute(delete(KnowledgeEntry).where(KnowledgeEntry.shop_id == shop.id))
            db.add_all(
                KnowledgeEntry(shop_id=shop.id, section=section, title=title, content=content)
                for section, title, content in KNOWLEDGE
            )
        await db.commit()

    print(f"Javab's own shop is ready (slug {slug}), owned by {email}.")
    if password:
        print(f"New account password (shown once): {password}")
    print("Log in with it to edit what the assistant knows, and link its Telegram in the panel.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # Persian text on the Windows console
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--email", required=True)
    parser.add_argument("--reset-knowledge", action="store_true")
    parser.add_argument("--take-over", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.email, args.reset_knowledge, args.take_over))
