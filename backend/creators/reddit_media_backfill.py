"""Re-read imported Reddit posts and fix their media.

Posts imported before galleries and Reddit-hosted videos were handled hold
only the first gallery image, or a still where the video was. This reads
each one back from Reddit (by id, 100 at a time) and rebuilds its body with
the importer's current rules. A post whose rebuilt body is the same, or
which is no longer on Reddit, is left alone.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from creators.post_import import (
    org_reddit_token,
    parse_reddit_child,
    reddit_post_content,
    youtube_id_from_url,
)
from posts.models import EvePost
from reddit.client import RedditClient

logger = logging.getLogger(__name__)

REDDIT_ID_RE = re.compile(
    r"\[Posted on Reddit\]\(https://(?:www\.)?reddit\.com/r/[^/]+/comments/(\w+)/"
)
BATCH = 100


@dataclass
class MediaFix:
    post_id: int
    title: str
    reason: str
    content: str


def reddit_id(content: str) -> str | None:
    match = REDDIT_ID_RE.search(content or "")
    return match.group(1) if match else None


def _fetch(ids: list[str], token: str) -> dict[str, dict]:
    response = requests.get(
        "https://oauth.reddit.com/by_id/" + ",".join(f"t3_{i}" for i in ids),
        headers={
            "Authorization": f"bearer {token}",
            "User-Agent": RedditClient().user_agent,
        },
        params={"raw_json": 1},
        timeout=20,
    )
    response.raise_for_status()
    children = (response.json().get("data") or {}).get("children") or []
    return {
        (c.get("data") or {}).get("id"): c.get("data") or {} for c in children
    }


def rebuilt_content(data: dict) -> tuple[str, str] | None:
    """The post body under the current rules, and why it changed: a gallery
    or a Reddit video. None for posts the old rules already got right."""
    item = parse_reddit_child(data, datetime.fromtimestamp(0, timezone.utc))
    if item is None or youtube_id_from_url(item["link_url"]):
        return None
    if item["video_embed_url"]:
        reason = "reddit video"
    elif len(item["image_urls"]) > 1:
        reason = f"gallery of {len(item['image_urls'])}"
    else:
        return None
    content = reddit_post_content(
        permalink=item["permalink"],
        image_url=item["image_url"],
        selftext=(item["selftext"] or "").strip(),
        image_urls=item["image_urls"],
        video_embed_url=item["video_embed_url"],
        title=item["title"],
    )
    return content, reason


def find_media_fixes(token: str) -> list[MediaFix]:
    posts = {
        rid: post
        for post in EvePost.objects.filter(
            content__contains="[Posted on Reddit]"
        ).only("id", "title", "content")
        if (rid := reddit_id(post.content))
    }
    ids = list(posts)
    fixes: list[MediaFix] = []
    for start in range(0, len(ids), BATCH):
        batch = ids[start : start + BATCH]
        try:
            found = _fetch(batch, token)
        except requests.RequestException as exc:
            logger.warning("Reddit by_id failed: %s", exc)
            continue
        for rid in batch:
            data = found.get(rid)
            if not data:
                continue
            rebuilt = rebuilt_content(data)
            post = posts[rid]
            if rebuilt and rebuilt[0] != post.content:
                fixes.append(
                    MediaFix(post.id, post.title, rebuilt[1], rebuilt[0])
                )
        time.sleep(0.35)
    return fixes


def apply_media_fixes(fixes: list[MediaFix]) -> int:
    for fix in fixes:
        EvePost.objects.filter(pk=fix.post_id).update(content=fix.content)
    return len(fixes)


def backfill_reddit_media(*, apply: bool = False) -> list[MediaFix]:
    token = org_reddit_token()
    if not token:
        raise RuntimeError("No Reddit token; set the org Reddit credentials.")
    fixes = find_media_fixes(token)
    if apply:
        apply_media_fixes(fixes)
    return fixes
