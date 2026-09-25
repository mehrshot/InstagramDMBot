"""The shop's Instagram posts: reading them, and linking each product to its post.

The bot shares a post when it recommends a product ("here's the post"), so the customer sees
the photos right in the DM. A product's post is the one the owner put in the product sheet
(post_url column), otherwise the newest post whose caption names the product or its code.
"""

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_secret
from app.core.text import normalize
from app.core.timeutil import utcnow
from app.models import InstagramAccount, InstagramPost, Product
from app.services.instagram import InstagramClient

logger = logging.getLogger(__name__)

# How a shared post is recorded in the conversation (panel and the bot's own history).
POST_MARKER = "[پست]"
MAX_POSTS_PER_REPLY = 3

_PERMALINK = re.compile(r"instagram\.com/(?:[\w.]+/)?(p|reel|tv)/([\w-]+)", re.IGNORECASE)


@dataclass(frozen=True)
class PostLink:
    # None when the owner linked a post we haven't read from Instagram: sent as a plain link.
    media_id: str | None
    permalink: str
    caption: str = ""
    preview_url: str | None = None


def post_key(url: str) -> str | None:
    """Stable identity of a post link ("p/ABC123"), whatever the domain, path or query."""
    match = _PERMALINK.search(url or "")
    return f"{match.group(1).lower()}/{match.group(2)}" if match else None


def shared_post_keys(texts: list[str]) -> set[str]:
    """Posts already sent in a conversation, from its message texts."""
    return {key for text in texts for key in [post_key(text)] if key}


async def sync_posts(
    db: AsyncSession, account: InstagramAccount, instagram: InstagramClient
) -> int:
    """Replace the shop's stored posts with what Instagram has now."""
    media = await instagram.list_media(decrypt_secret(account.access_token_encrypted))
    await db.execute(delete(InstagramPost).where(InstagramPost.shop_id == account.shop_id))
    for item in media:
        if not item.get("id") or not item.get("permalink"):
            continue
        db.add(
            InstagramPost(
                shop_id=account.shop_id,
                ig_media_id=str(item["id"]),
                permalink=item["permalink"],
                caption=(item.get("caption") or "")[:5000],
                media_type=str(item.get("media_type") or ""),
                preview_url=item.get("thumbnail_url") or item.get("media_url"),
                posted_at=_parse_time(item.get("timestamp")),
            )
        )
    account.posts_synced_at = utcnow()
    await db.commit()
    return len(media)


async def load_posts(db: AsyncSession, shop_id: uuid.UUID) -> list[InstagramPost]:
    return list(
        (await db.scalars(select(InstagramPost).where(InstagramPost.shop_id == shop_id))).all()
    )


def link_products(products: list[Product], posts: list[InstagramPost]) -> dict[str, PostLink]:
    """Map each product name to its post, if it has one."""
    by_key = {post_key(p.permalink): p for p in posts}
    newest_first = sorted(
        posts, key=lambda p: p.posted_at or datetime.min.replace(tzinfo=UTC), reverse=True
    )
    captions = [(p, normalize(p.caption)) for p in newest_first]

    links: dict[str, PostLink] = {}
    for product in products:
        name = product.name.strip()
        if name in links:
            continue
        # 1. The owner's explicit link wins.
        if product.post_url:
            post = by_key.get(post_key(product.post_url))
            links[name] = _link(post) if post else PostLink(None, product.post_url)
            continue
        # 2. Otherwise the newest post whose caption names the product (or its code).
        wanted = normalize(name)
        sku = (product.sku or "").strip().lower()
        for post, caption in captions:
            if (len(wanted) >= 3 and wanted in caption) or (
                sku and re.search(rf"(?<![\w-]){re.escape(sku)}(?![\w-])", caption)
            ):
                links[name] = _link(post)
                break
    return links


def _link(post: InstagramPost) -> PostLink:
    return PostLink(post.ig_media_id, post.permalink, post.caption, post.preview_url)


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        # Instagram sends "2026-09-20T10:15:30+0000"
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return None
