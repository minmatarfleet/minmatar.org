#!/usr/bin/env python3
"""Fetch latest topics from EVE Forums recruitment center."""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scout_lib import add_base_args, cutoff_from_days, emit, load_config_from_args  # noqa: E402


def strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return unescape(re.sub(r"\s+", " ", text)).strip()


def fetch_forum_latest(
    cutoff: datetime,
    category: str,
    user_agent: str,
    max_pages: int = 3,
) -> list[dict]:
    topics: list[dict] = []
    seen_ids: set[int] = set()

    for page in range(max_pages):
        resp = requests.get(
            f"https://forums.eveonline.com/c/{category}/l/latest.json",
            params={"page": page},
            timeout=20,
            headers={"User-Agent": user_agent},
        )
        if resp.status_code != 200:
            break

        topic_list = resp.json().get("topic_list", {})
        for topic in topic_list.get("topics", []):
            topic_id = topic.get("id")
            if not topic_id or topic_id in seen_ids:
                continue
            seen_ids.add(topic_id)

            last_posted_raw = topic.get("last_posted_at") or topic.get("created_at")
            if not last_posted_raw:
                continue
            last_posted = datetime.fromisoformat(last_posted_raw.replace("Z", "+00:00"))
            if last_posted < cutoff:
                continue

            title = topic.get("title", "")
            slug = topic.get("slug") or title.lower().replace(" ", "-")
            url = f"https://forums.eveonline.com/t/{slug}/{topic_id}"
            body = ""
            created = last_posted

            detail = requests.get(
                f"https://forums.eveonline.com/t/{slug}/{topic_id}.json",
                timeout=20,
                headers={"User-Agent": user_agent},
            )
            if detail.status_code == 200:
                posts = detail.json().get("post_stream", {}).get("posts", [])
                if posts:
                    body = strip_html(posts[0].get("cooked", ""))[:2000]
                    created_raw = posts[0].get("created_at")
                    if created_raw:
                        created = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))

            topics.append(
                {
                    "title": title,
                    "url": url,
                    "created": created.date().isoformat(),
                    "body": body,
                    "num_comments": topic.get("posts_count", 0),
                }
            )
            time.sleep(0.15)

        if not topic_list.get("more_topics_url"):
            break

    return topics


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch forum recruitment-center topics")
    add_base_args(parser)
    parser.add_argument("--days", type=int, default=7, help="Lookback window (default: 7)")
    parser.add_argument("--pages", type=int, default=3, help="Max pages to fetch (default: 3)")
    args = parser.parse_args()
    config = load_config_from_args(args)

    category = config.get("forums", {}).get(
        "recruitment_center_category", "recruitment-center"
    )
    cutoff = cutoff_from_days(args.days)
    topics = fetch_forum_latest(cutoff, category, args.user_agent, args.pages)

    payload = {
        "script": "fetch_forums",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "cutoff": cutoff.date().isoformat(),
        "days": args.days,
        "topics": topics,
        "summary": f"forums/{category}: {len(topics)} topics since {cutoff.date().isoformat()}",
    }
    emit(payload, args.json)


if __name__ == "__main__":
    main()
