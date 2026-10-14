#!/usr/bin/env python3
"""Fetch recent AARs / capital fight posts and videos from recruiter Reddit accounts.

Default source: u/BearThatCares submissions (r/Eve AARs, Bring Fun Shit, etc.).
The agent picks which links to weave into Rattini / FW redirect outreach.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scout_lib import (  # noqa: E402
    add_base_args,
    cutoff_from_days,
    emit,
    get_reddit_token,
    load_config_from_args,
    reddit_headers,
)

YOUTUBE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=[\w\-]+|youtu\.be/[\w\-]+|"
    r"youtube\.com/(?:shorts|live)/[\w\-]+)[^\s\)\]]*",
    re.IGNORECASE,
)
# Soft tags only — agent still chooses. Not used for routing.
HINT_RE = re.compile(
    r"\b(aar|after[\s\-]?action|dread|capital|carrier|fax|super|titan|"
    r"blops|blackops|siege|bring fun shit|ahbazon|amamake|fleet)\b",
    re.IGNORECASE,
)


def _normalize_youtube(url: str) -> str:
    url = url.rstrip(").,]")
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.netloc or "").lower().replace("www.", "")
    if host == "youtu.be":
        vid = parsed.path.strip("/").split("/")[0]
        return f"https://youtu.be/{vid}" if vid else url
    if "youtube.com" in host:
        if "watch" in parsed.path and "v=" in parsed.query:
            for part in parsed.query.split("&"):
                if part.startswith("v="):
                    return f"https://www.youtube.com/watch?v={part[2:]}"
        parts = [p for p in parsed.path.split("/") if p]
        if parts and parts[0] in ("shorts", "live") and len(parts) > 1:
            return f"https://www.youtube.com/{parts[0]}/{parts[1]}"
    return url


def _extract_youtube(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in YOUTUBE_RE.findall(text or ""):
        norm = _normalize_youtube(match)
        if norm not in seen:
            seen.add(norm)
            found.append(norm)
    return found


def _hint_tags(title: str, body: str) -> list[str]:
    blob = f"{title}\n{body}"
    tags = sorted({m.group(1).lower() for m in HINT_RE.finditer(blob)})
    if _extract_youtube(blob):
        tags.append("youtube")
    return tags


def fetch_user_submissions(
    account: str,
    cutoff: datetime,
    token: str | None,
    user_agent: str,
) -> list[dict]:
    if not token:
        return []

    posts: list[dict] = []
    after: str | None = None

    while True:
        url = (
            f"https://oauth.reddit.com/user/{account}/submitted.json"
            f"?limit=100&sort=new"
        )
        if after:
            url += f"&after={after}"

        resp = requests.get(url, headers=reddit_headers(user_agent, token), timeout=15)
        if resp.status_code >= 400:
            break

        payload = resp.json()
        children = payload.get("data", {}).get("children", [])
        if not children:
            break

        stop = False
        for child in children:
            data = child["data"]
            created = datetime.fromtimestamp(data["created_utc"], tz=timezone.utc)
            if created < cutoff:
                stop = True
                break

            title = data.get("title", "")
            body = data.get("selftext") or data.get("url") or ""
            media_url = data.get("url_overridden_by_dest") or data.get("url") or ""
            youtube = _extract_youtube(f"{body}\n{media_url}")
            if media_url and any(
                h in media_url.lower() for h in ("youtube.com", "youtu.be")
            ):
                youtube = list(dict.fromkeys(youtube + [_normalize_youtube(media_url)]))

            posts.append(
                {
                    "author": account,
                    "title": title,
                    "url": "https://www.reddit.com" + data.get("permalink", ""),
                    "subreddit": data.get("subreddit"),
                    "created": created.date().isoformat(),
                    "score": data.get("score"),
                    "youtube": youtube,
                    "hints": _hint_tags(title, f"{body}\n{media_url}"),
                    "is_video": bool(data.get("is_video")) or bool(youtube),
                }
            )

        if stop:
            break

        after = payload.get("data", {}).get("after")
        if not after:
            break
        time.sleep(0.2)

    return posts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch recent AARs / capital videos from recruiter Reddit accounts"
    )
    add_base_args(parser)
    parser.add_argument(
        "--days",
        type=int,
        default=45,
        help="Lookback window (default: 45)",
    )
    parser.add_argument(
        "--account",
        action="append",
        dest="accounts",
        help="Reddit username to scan (repeatable; default from config)",
    )
    args = parser.parse_args()
    config = load_config_from_args(args)

    reddit_cfg = config.get("reddit", {})
    accounts = args.accounts or reddit_cfg.get("proof_accounts") or ["BearThatCares"]
    token = get_reddit_token(args.user_agent)
    cutoff = cutoff_from_days(args.days)

    posts: list[dict] = []
    for account in accounts:
        posts.extend(fetch_user_submissions(account, cutoff, token, args.user_agent))
        time.sleep(0.2)

    # Prefer likely AAR / capital / video posts first for agent skim
    def sort_key(p: dict) -> tuple:
        hints = set(p.get("hints") or [])
        weight = 0
        if p.get("youtube") or p.get("is_video"):
            weight += 3
        if hints & {"aar", "after-action", "after action", "dread", "capital"}:
            weight += 2
        if hints & {"siege", "ahbazon", "bring fun shit"}:
            weight += 1
        return (-weight, p.get("created") or "", p.get("title") or "")

    posts_sorted = sorted(posts, key=sort_key)
    youtube_links = []
    seen_yt: set[str] = set()
    for p in posts_sorted:
        for yt in p.get("youtube") or []:
            if yt not in seen_yt:
                seen_yt.add(yt)
                youtube_links.append({"url": yt, "from_title": p.get("title"), "post": p.get("url")})

    payload = {
        "script": "fetch_proof_media",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "accounts": accounts,
        "cutoff": cutoff.date().isoformat(),
        "days": args.days,
        "reddit_oauth_available": token is not None,
        "posts": posts_sorted,
        "youtube_links": youtube_links,
        "summary": (
            f"proof media: {len(posts_sorted)} posts / {len(youtube_links)} youtube "
            f"from {', '.join('u/' + a for a in accounts)} since {cutoff.date().isoformat()}"
            if token
            else "proof media: skipped (load REDDIT_* from backend/.env)"
        ),
    }
    emit(payload, args.json)


if __name__ == "__main__":
    main()
