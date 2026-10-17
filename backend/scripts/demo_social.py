"""Demo data beyond DMs for scripts/seed_demo.py: comments, stories and page insights.

The numbers are made up but shaped like a small Iranian boutique's page, so every panel
screen has something real-looking to show.
"""

import io
import random
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CommentCategory,
    CommentStatus,
    InstagramComment,
    InstagramInsights,
    ScheduledStory,
    StoryStatus,
)
from app.services import stories

DRESS, SILK, SHIRT, STUDIO = (
    "17900000000000001",
    "17900000000000002",
    "17900000000000003",
    "17900000000000004",
)

# (username, post, text, category, status, minutes ago, private reply, public reply,
#  reason, hidden)
COMMENTS: list[tuple[Any, ...]] = [
    (
        "rana.k",
        DRESS,
        "قیمت این مانتو چنده؟",
        CommentCategory.PRICE,
        CommentStatus.ANSWERED,
        35,
        "سلام رعنا جان! مانتو کتان ۱,۲۵۰,۰۰۰ تومانه، مشکی و سرمه‌ای 🖤",
        "جزئیات رو دایرکت فرستادیم 💌",
        None,
        False,
    ),
    (
        "maya_h",
        DRESS,
        "مشکی ۴۰ داری؟",
        CommentCategory.AVAILABILITY,
        CommentStatus.ANSWERED,
        80,
        "بله عزیزم، مشکی سایز ۴۰ موجوده، ۱,۲۵۰,۰۰۰ تومان 🖤",
        "دایرکتتو چک کن 💌",
        None,
        False,
    ),
    (
        "lili.style",
        SILK,
        "😍😍",
        CommentCategory.PRAISE,
        CommentStatus.ANSWERED,
        120,
        None,
        "🙏🤍",
        None,
        False,
    ),
    (
        "nazanin.b",
        SHIRT,
        "به مشهد هم ارسال دارید؟",
        CommentCategory.ORDER,
        CommentStatus.ANSWERED,
        200,
        "بله! با پست پیشتاز ۳ تا ۵ روز کاری، هزینه ۸۵ هزار تومان (بالای ۲ میلیون رایگان).",
        "بله حتما، جزئیات رو دایرکت فرستادیم 💌",
        None,
        False,
    ),
    (
        "kimia_m",
        DRESS,
        "برای بوتیکم ۲۰ تا می‌خوام، قیمت عمده چنده؟",
        CommentCategory.ORDER,
        CommentStatus.UNANSWERED,
        25,
        None,
        None,
        "قیمت عمده در اطلاعات فروشگاه نیست",
        False,
    ),
    (
        "ali.k",
        SILK,
        "یک هفته‌ست سفارشم نرسیده!",
        CommentCategory.COMPLAINT,
        CommentStatus.UNANSWERED,
        50,
        None,
        None,
        "شکایت از دیر رسیدن سفارش",
        False,
    ),
    (
        "sara.fit",
        DRESS,
        "سرمه‌ای ۴۴ دوباره میاد؟",
        CommentCategory.AVAILABILITY,
        CommentStatus.UNANSWERED,
        90,
        None,
        None,
        "زمان موجود شدن دوباره مشخص نیست",
        False,
    ),
    (
        "dorsa_r",
        SHIRT,
        "پارچه‌ش نازکه؟ بدن‌نما نیست؟",
        CommentCategory.PRODUCT,
        CommentStatus.UNANSWERED,
        140,
        None,
        None,
        "ضخامت پارچه در اطلاعات فروشگاه نیست",
        False,
    ),
    (
        "mina_h",
        STUDIO,
        "@maya_h @lili.style 👀",
        CommentCategory.OTHER,
        CommentStatus.SKIPPED,
        300,
        None,
        None,
        None,
        False,
    ),
    (
        "follower.shop",
        DRESS,
        "۱۰ هزار فالوور واقعی فقط امروز 👈 cheapfollows.biz",
        CommentCategory.SPAM,
        CommentStatus.SKIPPED,
        400,
        None,
        None,
        None,
        True,
    ),
]

# (title, subtitle, colours, note, hours from now, status). The image text stays Latin: the
# default font has no Persian letters.
STORIES = [
    (
        "NEW IN",
        "Linen manto",
        ((24, 24, 27), (80, 70, 60)),
        "مانتو کتان جدید، مشکی و سرمه‌ای، ۱,۲۵۰,۰۰۰ تومان، سایز ۴۰ تا ۴۴",
        -5,
        StoryStatus.PUBLISHED,
    ),
    (
        "WEEKEND SALE",
        "15% off silk blouses",
        ((37, 72, 224), (120, 150, 255)),
        "حراج آخر هفته: ۱۵٪ تخفیف همه شومیزهای حریر، فقط پنجشنبه و جمعه",
        20,
        StoryStatus.SCHEDULED,
    ),
    (
        "BACK IN STOCK",
        "Cream linen shirt",
        ((176, 137, 92), (236, 220, 196)),
        "شومیز لینن کرم دوباره موجود شد، ۹۵۰,۰۰۰ تومان، فری‌سایز",
        46,
        StoryStatus.SCHEDULED,
    ),
]


def story_image(title: str, subtitle: str, colours: tuple[tuple[int, int, int], ...]) -> bytes:
    """A simple 1080x1920 story: a vertical gradient with two lines of text."""
    from PIL import Image, ImageDraw, ImageFont

    top, bottom = colours
    image = Image.new("RGB", (1080, 1920))
    draw = ImageDraw.Draw(image)
    for y in range(1920):
        t = y / 1919
        draw.line(
            [(0, y), (1080, y)],
            fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom, strict=True)),
        )
    big, small = ImageFont.load_default(size=120), ImageFont.load_default(size=64)
    for text, font, y in ((title, big, 820), (subtitle, small, 1000)):
        width = draw.textlength(text, font=font)
        draw.text(((1080 - width) / 2, y), text, font=font, fill=(255, 255, 255))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=88)
    return out.getvalue()


def insights_data(now: datetime) -> dict[str, Any]:
    rng = random.Random(7)
    media = []
    formats = ["REELS", "CAROUSEL_ALBUM", "IMAGE", "REELS", "IMAGE", "CAROUSEL_ALBUM"]
    captions = [
        "سه مدل ست کردن مانتو کتان 🖤 #مانتو #مانتو_کتان",
        "شومیز حریر سفید رسید 🤍 #شومیز #تولید_ایران",
        "شومیز لینن کرم دوباره موجود شد ☀️ #مانتو_کتان",
        "پشت صحنه عکاسی کالکشن جدید 📸 #مزون #کسب_و_کار_کوچک",
        "کارگاه ما در تهران ✨",
        "رنگ‌های تابستونی رسیدن #تابستان #مانتو",
    ]
    for i in range(14):
        kind = formats[i % len(formats)]
        reel = kind == "REELS"
        # Wednesday and Thursday evenings do best on this page.
        posted = now - timedelta(days=2 + i * 2.3)
        posted = posted.replace(hour=rng.choice([10, 13, 18, 19, 21]), minute=0)
        boost = 1.6 if posted.weekday() in (2, 3) and posted.hour >= 18 else 1.0
        reach = int(
            (3400 if reel else 950 if kind == "CAROUSEL_ALBUM" else 620)
            * boost
            * rng.uniform(0.75, 1.3)
        )
        likes = int(reach * rng.uniform(0.06, 0.1))
        comments = int(likes * rng.uniform(0.05, 0.15))
        saves = int(reach * (0.025 if reel else 0.012))
        shares = int(reach * (0.012 if reel else 0.004))
        media.append(
            {
                "id": f"1790000000000{1000 + i}",
                "caption": captions[i % len(captions)],
                "media_type": "VIDEO" if reel else kind,
                "product_type": "REELS" if reel else "FEED",
                "permalink": f"https://www.instagram.com/p/DEMO{i:04d}/",
                "preview_url": None,
                "timestamp": posted.strftime("%Y-%m-%dT%H:%M:%S+0000"),
                "likes": likes,
                "comments": comments,
                "reach": reach,
                "views": int(reach * (2.4 if reel else 1.3)),
                "saves": saves,
                "shares": shares,
                "interactions": likes + comments + saves + shares,
            }
        )
    days = [(now - timedelta(days=30 - d)).strftime("%Y-%m-%d") for d in range(30)]
    return {
        "profile": {
            "username": "mahsa.boutique",
            "name": "مزون مهسا",
            "picture_url": None,
            "followers": 4820,
            "follows": 312,
            "posts": 186,
        },
        "week": {
            "reach": 11840,
            "views": 26310,
            "accounts_engaged": 1210,
            "total_interactions": 1645,
            "likes": 1290,
            "comments": 142,
            "shares": 96,
            "saves": 117,
            "follows_and_unfollows": 64,
            "profile_links_taps": 38,
        },
        "previous_week": {
            "reach": 9720,
            "views": 22040,
            "accounts_engaged": 1080,
            "total_interactions": 1390,
            "likes": 1104,
            "comments": 121,
            "shares": 71,
            "saves": 94,
            "follows_and_unfollows": 41,
            "profile_links_taps": 33,
        },
        "series": {
            "reach": [
                {
                    "date": day,
                    "value": int(
                        1300 + 500 * ((i % 7) in (2, 3)) + i * 18 + rng.randint(-150, 150)
                    ),
                }
                for i, day in enumerate(days)
            ],
            "follower_count": [
                {"date": day, "value": max(0, 6 + (i // 6) + rng.randint(-3, 5))}
                for i, day in enumerate(days)
            ],
        },
        "media": media,
    }


async def seed(db: AsyncSession, shop_id: uuid.UUID, now: datetime) -> None:
    for (
        username,
        post,
        text,
        category,
        state,
        minutes,
        private,
        public,
        reason,
        hidden,
    ) in COMMENTS:
        db.add(
            InstagramComment(
                shop_id=shop_id,
                ig_comment_id=f"demo-comment-{uuid.uuid4().hex[:10]}",
                media_id=post,
                media_permalink=f"https://www.instagram.com/p/{post[-6:]}/",
                media_caption={
                    DRESS: "مانتو کتان ترک 🖤 مشکی و سرمه‌ای، سایز ۴۰ تا ۴۴\nکد M-101",
                    SILK: "شومیز حریر سفید، سبک و خنک 🤍 فری‌سایز",
                    SHIRT: "شومیز لینن کرم ☀️ مناسب تابستون",
                    STUDIO: "پشت صحنه‌ی عکاسی کالکشن جدید 📸",
                }[post],
                media_product_type="FEED",
                author_id=f"8800000000000{len(username)}{minutes}",
                author_username=username,
                text=text,
                commented_at=now - timedelta(minutes=minutes),
                status=state,
                category=category,
                reason=reason,
                public_reply=public,
                public_reply_id=f"demo-reply-{minutes}" if public else None,
                private_reply=private,
                private_reply_sent=bool(private),
                hidden=hidden,
                handled_at=now - timedelta(minutes=minutes - 1),
                prompt_tokens=1200
                if state == CommentStatus.ANSWERED and category != CommentCategory.PRAISE
                else None,
                completion_tokens=60
                if state == CommentStatus.ANSWERED and category != CommentCategory.PRAISE
                else None,
            )
        )

    for index, (title, subtitle, colours, note, hours, state) in enumerate(STORIES):
        story_id = uuid.uuid4()
        name = f"{story_id.hex}.jpg"
        content = story_image(title, subtitle, colours)
        (stories.media_root() / name).write_bytes(content)
        when = now + timedelta(hours=hours)
        db.add(
            ScheduledStory(
                id=story_id,
                shop_id=shop_id,
                media_kind="image",
                file_name=name,
                content_type="image/jpeg",
                size_bytes=len(content),
                token=secrets.token_urlsafe(24),
                note=note,
                scheduled_at=when.replace(minute=0, second=0, microsecond=0),
                status=state,
                ig_media_id=f"demo-story-{index}" if state == StoryStatus.PUBLISHED else None,
                published_at=when if state == StoryStatus.PUBLISHED else None,
            )
        )

    db.add(
        InstagramInsights(
            shop_id=shop_id, data=insights_data(now), fetched_at=now - timedelta(hours=3)
        )
    )
