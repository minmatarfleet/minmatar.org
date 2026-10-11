"""Turn linked Reddit / YouTube creator media into EvePost drafts or publishes."""

from __future__ import annotations

import html
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any, Iterable
from urllib.parse import unquote

import requests
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from creators.clients.reddit import normalize_reddit_username
from creators.models import CreatorAccount, CreatorProvider
from creators.oauth import OAuthError, refresh_access_token
from posts.models import EvePost, EveTag
from reddit.client import RedditClient

logger = logging.getLogger(__name__)

EVE_SUBREDDITS = frozenset({"eve", "evememes"})
YOUTUBE_API = "https://www.googleapis.com/youtube/v3"
YOUTUBE_ID_RE = re.compile(
    r"(?:youtube\.com/watch\?v=|youtube\.com/embed/|"
    r"youtube\.com/shorts/|youtu\.be/|videoid=[\"']?)([A-Za-z0-9_-]{11})",
    re.I,
)
REDDIT_ID_RE = re.compile(
    r"reddit\.com/r/[^/\s)]+/comments/([a-z0-9]+)",
    re.I,
)
ATOM_NS = "{http://www.w3.org/2005/Atom}"
YT_NS = "{http://www.youtube.com/xml/schemas/2015}"


@dataclass
class ImportCandidate:
    provider: str
    external_id: str
    title: str
    url: str
    published_at: datetime
    suggested_tag: str
    content: str
    seo_description: str
    author_username: str
    skip_reason: str | None = None


def collect_candidates(
    accounts: Iterable[CreatorAccount],
    *,
    cutoff: datetime,
    reddit_token: str | None,
) -> list[ImportCandidate]:
    candidates: list[ImportCandidate] = []
    warned_reddit = False
    for account in accounts:
        if account.provider == CreatorProvider.REDDIT:
            if not reddit_token:
                if not warned_reddit:
                    logger.warning("Skipping Reddit import: no org token")
                    warned_reddit = True
                continue
            raw_items = fetch_reddit_window(
                account.platform_username or account.platform_user_id,
                reddit_token,
                cutoff=cutoff,
            )
            username = account.user.username
            for item in raw_items:
                candidates.append(candidate_from_reddit(item, username))
        elif account.provider == CreatorProvider.YOUTUBE:
            raw_items = fetch_youtube_window(account, cutoff=cutoff)
            username = account.user.username
            for item in raw_items:
                candidates.append(candidate_from_youtube(item, username))
    return candidates


def candidate_from_reddit(
    item: dict[str, Any], author_username: str
) -> ImportCandidate:
    tag, skip = classify_reddit(item)
    title = (item.get("title") or "Untitled Reddit post")[:250]
    permalink = item.get("permalink") or item.get("url") or ""
    link_url = item.get("link_url") or ""
    image_url = item.get("image_url") or ""
    selftext = (item.get("selftext") or "").strip()
    video_id = youtube_id_from_url(link_url)
    if video_id:
        content = youtube_post_content(video_id)
        if permalink:
            content = (
                content.rstrip() + f"\n\n[Posted on Reddit]({permalink})\n"
            )
        url = f"https://www.youtube.com/watch?v={video_id}"
    else:
        content = reddit_post_content(
            permalink=permalink,
            image_url=image_url,
            selftext=selftext,
        )
        url = permalink
    seo = (selftext or title).replace("\n", " ").strip()[:300]
    return ImportCandidate(
        provider=CreatorProvider.REDDIT,
        external_id=str(item.get("id") or ""),
        title=title,
        url=url,
        published_at=item["published_at"],
        suggested_tag=tag,
        content=content,
        seo_description=seo,
        author_username=author_username,
        skip_reason=skip,
    )


def candidate_from_youtube(
    item: dict[str, Any], author_username: str
) -> ImportCandidate:
    video_id = str(item.get("id") or "")
    title = (item.get("title") or "Untitled video")[:250]
    url = item.get("url") or f"https://www.youtube.com/watch?v={video_id}"
    return ImportCandidate(
        provider=CreatorProvider.YOUTUBE,
        external_id=video_id,
        title=title,
        url=url,
        published_at=item["published_at"],
        suggested_tag="Videos",
        content=youtube_post_content(video_id),
        seo_description=title[:300],
        author_username=author_username,
    )


def classify_reddit(item: dict[str, Any]) -> tuple[str, str | None]:
    if item.get("removed"):
        return "Propaganda", "removed"
    sub = (item.get("subreddit") or "").lower()
    if sub not in EVE_SUBREDDITS:
        return "Propaganda", f"subreddit:{sub or 'unknown'}"
    link_url = item.get("link_url") or item.get("url") or ""
    if youtube_id_from_url(link_url):
        return "Videos", None
    if item.get("is_self"):
        return "Dispatches", None
    return "Propaganda", None


def youtube_id_from_url(url: str) -> str | None:
    if not url:
        return None
    match = YOUTUBE_ID_RE.search(url)
    return match.group(1) if match else None


def reddit_post_content(
    *, permalink: str, image_url: str, selftext: str
) -> str:
    parts: list[str] = []
    if image_url:
        parts.append(f"![image]({image_url})")
    if selftext:
        parts.append(rewrite_reddit_inline_images(selftext))
    if permalink:
        parts.append(f"[Posted on Reddit]({permalink})")
    return "\n\n".join(parts).strip() + "\n"


_REDDIT_IMAGE_URL = (
    r"https://(?:preview\.redd\.it|external-preview\.redd\.it|"
    r"i\.redd\.it|i\.imgur\.com)/[^\s)]+"
)


def rewrite_reddit_inline_images(text: str) -> str:
    if not text:
        return text
    rewritten = re.sub(
        rf"(?<!!)\[([^\]]*)\]\(({_REDDIT_IMAGE_URL})\)",
        r"![\1](\2)",
        text,
    )
    rewritten = re.sub(
        rf"(?m)^({_REDDIT_IMAGE_URL})\s*$",
        r"![image](\1)",
        rewritten,
    )
    return rewritten


def youtube_post_content(video_id: str) -> str:
    thumb = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
    return (
        f'<div class="hidden">\n![image]({thumb})\n</div>\n'
        f'<lite-youtube videoid="{video_id}" '
        f'posterquality="maxresdefault" autoload></lite-youtube>\n'
    )


def fetch_reddit_window(
    username: str, token: str, *, cutoff: datetime
) -> list[dict[str, Any]]:
    name = normalize_reddit_username(username)
    if not name:
        return []
    headers = {
        "Authorization": f"bearer {token}",
        "User-Agent": RedditClient().user_agent,
    }
    after = None
    out: list[dict[str, Any]] = []
    page_count = 0
    while page_count < 20:
        page_count += 1
        params: dict[str, Any] = {"limit": 100, "raw_json": 1}
        if after:
            params["after"] = after
        response = requests.get(
            f"https://oauth.reddit.com/user/{name}/submitted",
            headers=headers,
            params=params,
            timeout=20,
        )
        if response.status_code >= 400:
            logger.warning(
                "Reddit submitted failed for %s: %s %s",
                name,
                response.status_code,
                response.text[:200],
            )
            break
        data = response.json().get("data") or {}
        children = data.get("children") or []
        if not children:
            break
        stop = False
        for child in children:
            parsed = parse_reddit_child(child.get("data") or {}, cutoff)
            if parsed is None:
                created = (child.get("data") or {}).get("created_utc")
                if created is not None:
                    published = datetime.fromtimestamp(
                        float(created), tz=dt_timezone.utc
                    )
                    if published < cutoff:
                        stop = True
                continue
            out.append(parsed)
        after = data.get("after")
        if stop or not after:
            break
        time.sleep(0.35)
    return out


def parse_reddit_child(
    data: dict[str, Any], cutoff: datetime
) -> dict[str, Any] | None:
    created = data.get("created_utc")
    if created is None:
        return None
    published = datetime.fromtimestamp(float(created), tz=dt_timezone.utc)
    if published < cutoff:
        return None
    post_id = data.get("id") or data.get("name") or ""
    if isinstance(post_id, str) and post_id.startswith("t3_"):
        post_id = post_id[3:]
    if not post_id:
        return None
    permalink = data.get("permalink") or ""
    if permalink and not permalink.startswith("http"):
        permalink = "https://www.reddit.com" + permalink
    link_url = data.get("url") or ""
    return {
        "id": str(post_id),
        "title": data.get("title") or "",
        "url": permalink or link_url,
        "permalink": permalink,
        "link_url": link_url,
        "subreddit": (data.get("subreddit") or "").lower(),
        "is_self": bool(data.get("is_self")),
        "post_hint": data.get("post_hint") or "",
        "removed": bool(data.get("removed_by_category")),
        "selftext": data.get("selftext") or "",
        "image_url": reddit_image_url(data),
        "published_at": published,
    }


def reddit_image_url(data: dict[str, Any]) -> str:
    url = _clean_media_url(data.get("url") or "")
    if _looks_like_image(url):
        return url
    images = (data.get("preview") or {}).get("images") or []
    if images:
        source = _clean_media_url(
            (images[0].get("source") or {}).get("url") or ""
        )
        if source:
            return source
    gallery = data.get("gallery_data") or {}
    metadata = data.get("media_metadata") or {}
    items = gallery.get("items") or []
    if items:
        media_id = items[0].get("media_id")
        meta = metadata.get(media_id) or {}
        source = _clean_media_url((meta.get("s") or {}).get("u") or "")
        if source:
            return source
    return ""


def _looks_like_image(url: str) -> bool:
    lower = url.lower()
    return any(
        token in lower
        for token in (
            "i.redd.it",
            "i.imgur.com",
            "preview.redd.it",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
        )
    )


def _clean_media_url(url: str) -> str:
    return unquote(html.unescape(url or ""))


def fetch_youtube_window(
    account: CreatorAccount, *, cutoff: datetime
) -> list[dict[str, Any]]:
    token = _youtube_access_token(account)
    if token:
        items = _youtube_playlist_window(account, token, cutoff)
        if items:
            return items
    return _youtube_rss_window(account.platform_user_id, cutoff)


def _youtube_access_token(account: CreatorAccount) -> str | None:
    if account.access_token and not account.token_invalid:
        expires = account.token_expires_at
        if expires is None or expires > timezone.now() + timedelta(minutes=2):
            return account.access_token
    if not account.refresh_token:
        return account.access_token or None
    try:
        payload = refresh_access_token(
            CreatorProvider.YOUTUBE, account.refresh_token
        )
    except OAuthError:
        logger.warning(
            "YouTube refresh failed for account %s; using RSS fallback",
            account.id,
        )
        return None
    return payload.access_token


def _youtube_playlist_window(
    account: CreatorAccount, token: str, cutoff: datetime
) -> list[dict[str, Any]]:
    uploads_id = (account.extra or {}).get("uploads_playlist_id") or ""
    headers = {"Authorization": f"Bearer {token}"}
    if not uploads_id:
        response = requests.get(
            f"{YOUTUBE_API}/channels",
            headers=headers,
            params={"part": "snippet,contentDetails", "mine": "true"},
            timeout=20,
        )
        if response.status_code >= 400:
            logger.warning(
                "YouTube channels.list failed: %s %s",
                response.status_code,
                response.text[:200],
            )
            return []
        items = response.json().get("items") or []
        if not items:
            return []
        related = (items[0].get("contentDetails") or {}).get(
            "relatedPlaylists"
        ) or {}
        uploads_id = related.get("uploads") or ""
    if not uploads_id:
        return []

    out: list[dict[str, Any]] = []
    page_token = None
    page_count = 0
    while page_count < 20:
        page_count += 1
        params: dict[str, Any] = {
            "part": "snippet,contentDetails",
            "playlistId": uploads_id,
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token
        response = requests.get(
            f"{YOUTUBE_API}/playlistItems",
            headers=headers,
            params=params,
            timeout=20,
        )
        if response.status_code >= 400:
            logger.warning(
                "YouTube playlistItems failed: %s %s",
                response.status_code,
                response.text[:200],
            )
            break
        payload = response.json()
        stop = False
        for item in payload.get("items") or []:
            parsed = parse_youtube_playlist_item(item, cutoff)
            if parsed is None:
                content = item.get("contentDetails") or {}
                snippet = item.get("snippet") or {}
                ts = content.get("videoPublishedAt") or snippet.get(
                    "publishedAt"
                )
                published = _parse_ts(ts)
                if published and published < cutoff:
                    stop = True
                continue
            out.append(parsed)
        page_token = payload.get("nextPageToken")
        if stop or not page_token:
            break
        time.sleep(0.2)
    return out


def parse_youtube_playlist_item(
    item: dict[str, Any], cutoff: datetime
) -> dict[str, Any] | None:
    content = item.get("contentDetails") or {}
    snippet = item.get("snippet") or {}
    video_id = content.get("videoId") or ""
    published = _parse_ts(
        content.get("videoPublishedAt") or snippet.get("publishedAt")
    )
    if not video_id or published is None or published < cutoff:
        return None
    return {
        "id": video_id,
        "title": snippet.get("title") or "",
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "published_at": published,
    }


def _youtube_rss_window(
    channel_id: str, cutoff: datetime
) -> list[dict[str, Any]]:
    if not channel_id:
        return []
    response = requests.get(
        f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}",
        timeout=20,
    )
    if response.status_code >= 400:
        logger.warning(
            "YouTube RSS failed for %s: %s", channel_id, response.status_code
        )
        return []
    root = ET.fromstring(response.content)
    out: list[dict[str, Any]] = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        video_el = entry.find(f"{YT_NS}videoId")
        title_el = entry.find(f"{ATOM_NS}title")
        published_el = entry.find(f"{ATOM_NS}published")
        video_id = video_el.text if video_el is not None else ""
        published = _parse_ts(
            published_el.text if published_el is not None else None
        )
        if not video_id or published is None or published < cutoff:
            continue
        out.append(
            {
                "id": video_id,
                "title": title_el.text if title_el is not None else "",
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "published_at": published,
            }
        )
    return out


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = parse_datetime(value.replace("Z", "+00:00"))
    if dt and timezone.is_naive(dt):
        dt = timezone.make_aware(dt, dt_timezone.utc)
    return dt


def existing_post_fingerprints(
    posts: Iterable[EvePost],
) -> tuple[set[str], set[str], set[str]]:
    youtube_ids: set[str] = set()
    reddit_ids: set[str] = set()
    titles: set[str] = set()
    for post in posts:
        blob = f"{post.title}\n{post.content or ''}"
        youtube_ids.update(YOUTUBE_ID_RE.findall(blob))
        reddit_ids.update(rid.lower() for rid in REDDIT_ID_RE.findall(blob))
        titles.add(_norm_title(post.title))
    return youtube_ids, reddit_ids, titles


def _norm_title(title: str) -> str:
    return (
        re.sub(r"\s+", " ", (title or "").replace("\r", " ")).strip().lower()
    )


def partition_candidates(
    candidates: list[ImportCandidate],
    *,
    posts: Iterable[EvePost],
) -> tuple[list[ImportCandidate], list[ImportCandidate]]:
    youtube_ids, reddit_ids, titles = existing_post_fingerprints(posts)
    to_import: list[ImportCandidate] = []
    skipped: list[ImportCandidate] = []
    seen_ids: set[tuple[str, str]] = set()
    for candidate in candidates:
        key = (candidate.provider, candidate.external_id)
        if candidate.skip_reason:
            skipped.append(candidate)
            continue
        if key in seen_ids:
            candidate.skip_reason = "duplicate_in_batch"
            skipped.append(candidate)
            continue
        seen_ids.add(key)
        if _norm_title(candidate.title) in titles:
            candidate.skip_reason = "existing_title"
            skipped.append(candidate)
            continue
        content_youtube_ids = set(
            YOUTUBE_ID_RE.findall(candidate.content or "")
        )
        if (
            candidate.provider == CreatorProvider.YOUTUBE
            and candidate.external_id in youtube_ids
        ) or (content_youtube_ids & youtube_ids):
            candidate.skip_reason = "existing_youtube"
            skipped.append(candidate)
            continue
        if (
            candidate.provider == CreatorProvider.REDDIT
            and candidate.external_id.lower() in reddit_ids
        ):
            candidate.skip_reason = "existing_reddit"
            skipped.append(candidate)
            continue
        to_import.append(candidate)
    return to_import, skipped


def apply_imports(
    candidates: list[ImportCandidate],
    *,
    state: str = "published",
    dry_run: bool = False,
) -> list[EvePost]:
    created: list[EvePost] = []
    if dry_run:
        return created
    with transaction.atomic():
        for candidate in candidates:
            user = User.objects.filter(
                username=candidate.author_username
            ).first()
            if user is None:
                logger.warning(
                    "Skipping import; no local user %s",
                    candidate.author_username,
                )
                continue
            created.append(_create_post(candidate, user=user, state=state))
    return created


def _create_post(
    candidate: ImportCandidate, *, user: User, state: str
) -> EvePost:
    title = _unique_title(candidate.title)
    post = EvePost.objects.create(
        title=title,
        state=state,
        seo_description=candidate.seo_description[:300],
        slug=EvePost.generate_slug(title)[:100],
        content=candidate.content,
        user=user,
    )
    EvePost.objects.filter(pk=post.pk).update(
        date_posted=candidate.published_at
    )
    post.refresh_from_db()
    tag, _ = EveTag.objects.get_or_create(tag=candidate.suggested_tag)
    post.tags.set([tag])
    return post


def _unique_title(title: str) -> str:
    if not EvePost.objects.filter(title=title).exists():
        return title
    for suffix in (" (Reddit)", " (YouTube)", " (imported)"):
        candidate = (title[: 250 - len(suffix)]) + suffix
        if not EvePost.objects.filter(title=candidate).exists():
            return candidate
    return f"{title[:240]} ({timezone.now().strftime('%Y%m%d%H%M')})"


def org_reddit_token() -> str | None:
    return RedditClient().get_access_token()
