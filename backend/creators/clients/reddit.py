"""Reddit reads for creator accounts via the org password-grant client."""

from __future__ import annotations

import logging
from typing import Any

import requests

from reddit.client import RedditClient

logger = logging.getLogger(__name__)


def list_user_submitted(
    username: str, *, limit: int = 25
) -> list[dict[str, Any]]:
    """
    Fetch recent public submissions for a Reddit username using org credentials.
    Returns list of post dicts with id, title, url, created_utc, thumbnail.
    """
    name = normalize_reddit_username(username)
    if not name:
        return []

    client = RedditClient()
    token = client.get_access_token()
    if not token:
        return []

    response = requests.get(
        f"https://oauth.reddit.com/user/{name}/submitted",
        headers={
            "Authorization": f"bearer {token}",
            "User-Agent": client.user_agent,
        },
        params={"limit": min(limit, 100), "raw_json": 1},
        timeout=15,
    )
    if response.status_code >= 400:
        logger.warning(
            "Reddit user submitted failed for %s: %s %s",
            name,
            response.status_code,
            response.text[:200],
        )
        return []

    try:
        children = (response.json().get("data") or {}).get("children") or []
    except (ValueError, AttributeError, TypeError):
        return []

    results: list[dict[str, Any]] = []
    for child in children:
        data = child.get("data") or {}
        post_id = data.get("id") or data.get("name") or ""
        if isinstance(post_id, str) and post_id.startswith("t3_"):
            post_id = post_id[3:]
        if not post_id:
            continue
        permalink = data.get("permalink") or ""
        url = data.get("url") or ""
        if permalink and not permalink.startswith("http"):
            permalink = "https://www.reddit.com" + permalink
        thumb = data.get("thumbnail") or ""
        if thumb in ("self", "default", "nsfw", "spoiler", "image"):
            thumb = ""
        results.append(
            {
                "id": str(post_id),
                "title": data.get("title") or "",
                "url": permalink or url,
                "created_utc": data.get("created_utc"),
                "thumbnail": thumb,
                "subreddit": data.get("subreddit") or "",
            }
        )
    return results


def normalize_reddit_username(username: str) -> str:
    """
    Accept bare names, u/ prefixes, or profile URLs.
    Examples: BearThatCares, u/BearThatCares,
    https://www.reddit.com/user/BearThatCares/
    """
    name = (username or "").strip()
    if not name:
        return ""

    lower = name.lower()
    for marker in ("/user/", "/u/"):
        idx = lower.find(marker)
        if idx != -1:
            name = name[idx + len(marker) :]
            break
    else:
        if name.startswith("/u/"):
            name = name[3:]
        elif name.startswith("u/"):
            name = name[2:]

    # Drop path/query leftovers from URLs.
    name = name.split("?")[0].split("#")[0].strip().strip("/")
    if "/" in name:
        name = name.split("/")[0]
    return name.strip()
