#!/usr/bin/env python3
"""Fetch raw /new posts from configured subreddits (Reddit OAuth)."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

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


def reddit_post_record(data: dict) -> dict:
    created = datetime.fromtimestamp(data["created_utc"], tz=timezone.utc)
    return {
        "title": data.get("title", ""),
        "url": "https://www.reddit.com" + data.get("permalink", ""),
        "created": created.date().isoformat(),
        "body": (data.get("selftext") or "")[:2000],
        "flair": data.get("link_flair_text"),
        "subreddit": data.get("subreddit"),
        "num_comments": data.get("num_comments", 0),
    }


def fetch_reddit_new(
    cutoff: datetime,
    token: str | None,
    user_agent: str,
    subreddits: list[str],
) -> list[dict]:
    if not token:
        return []

    posts: list[dict] = []
    seen_ids: set[str] = set()

    for subreddit in subreddits:
        resp = requests.get(
            f"https://oauth.reddit.com/r/{subreddit}/new.json?limit=100",
            headers=reddit_headers(user_agent, token),
            timeout=15,
        )
        if resp.status_code >= 400:
            continue
        for child in resp.json().get("data", {}).get("children", []):
            data = child["data"]
            post_id = data.get("id")
            if not post_id or post_id in seen_ids:
                continue
            created = datetime.fromtimestamp(data["created_utc"], tz=timezone.utc)
            if created < cutoff:
                continue
            seen_ids.add(post_id)
            posts.append(reddit_post_record(data))
        time.sleep(0.2)

    return posts


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch raw subreddit /new posts")
    add_base_args(parser)
    parser.add_argument("--days", type=int, default=7, help="Lookback window (default: 7)")
    parser.add_argument(
        "--subreddit",
        action="append",
        dest="subreddits",
        help="Override config subreddit (repeatable)",
    )
    args = parser.parse_args()
    config = load_config_from_args(args)

    subreddits = args.subreddits or config.get("reddit", {}).get("subreddits", ["evejobs", "eve"])
    token = get_reddit_token(args.user_agent)
    cutoff = cutoff_from_days(args.days)
    posts = fetch_reddit_new(cutoff, token, args.user_agent, subreddits)

    payload = {
        "script": "fetch_reddit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "subreddits": subreddits,
        "cutoff": cutoff.date().isoformat(),
        "days": args.days,
        "reddit_oauth_available": token is not None,
        "posts": posts,
        "summary": (
            f"r/{', r/'.join(subreddits)}: {len(posts)} posts since {cutoff.date().isoformat()}"
            if token
            else "Skipped (load REDDIT_* from backend/.env)"
        ),
    }
    emit(payload, args.json)


if __name__ == "__main__":
    main()
