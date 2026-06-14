#!/usr/bin/env python3
"""Fetch recent recruitment ads from u/MinmatarFleet (Reddit OAuth)."""

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


def fetch_recruitment_ads(
    account: str,
    cutoff: datetime,
    token: str | None,
    user_agent: str,
) -> list[dict]:
    if not token:
        return []

    ads: list[dict] = []
    seen_titles: set[str] = set()
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
            if title in seen_titles:
                continue
            seen_titles.add(title)
            ads.append(
                {
                    "title": title,
                    "url": "https://www.reddit.com" + data.get("permalink", ""),
                    "subreddit": data.get("subreddit"),
                    "created": created.date().isoformat(),
                }
            )

        if stop:
            break

        after = payload.get("data", {}).get("after")
        if not after:
            break
        time.sleep(0.2)

    return ads


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch u/MinmatarFleet recruitment ads")
    add_base_args(parser)
    parser.add_argument("--days", type=int, default=30, help="Lookback window (default: 30)")
    args = parser.parse_args()
    config = load_config_from_args(args)

    account = config.get("reddit", {}).get("recruitment_account", "MinmatarFleet")
    token = get_reddit_token(args.user_agent)
    cutoff = cutoff_from_days(args.days)
    ads = fetch_recruitment_ads(account, cutoff, token, args.user_agent)

    payload = {
        "script": "fetch_recruitment_ads",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "account": account,
        "cutoff": cutoff.date().isoformat(),
        "days": args.days,
        "reddit_oauth_available": token is not None,
        "ads": ads,
        "summary": (
            f"u/{account}: {len(ads)} ads since {cutoff.date().isoformat()}"
            if token
            else f"u/{account}: skipped (load REDDIT_* from backend/.env)"
        ),
    }
    emit(payload, args.json)


if __name__ == "__main__":
    main()
