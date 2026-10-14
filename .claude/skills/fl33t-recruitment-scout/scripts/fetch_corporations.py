#!/usr/bin/env python3
"""Fetch corporation profiles from the public API."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scout_lib import (  # noqa: E402
    add_base_args,
    alliance_name_from_corps,
    emit,
    load_config_from_args,
)


def fetch_corporations(config: dict, user_agent: str) -> dict:
    base = config["api_base_url"].rstrip("/")
    corps: dict = {}
    for corp_type in config.get("corporation_types", ["alliance"]):
        resp = requests.get(
            f"{base}/eveonline/corporations/corporations",
            params={"corporation_type": corp_type},
            headers={"User-Agent": user_agent},
            timeout=30,
        )
        resp.raise_for_status()
        rows = []
        for item in resp.json():
            rows.append(
                {
                    "name": item.get("corporation_name"),
                    "corporation_id": item.get("corporation_id"),
                    "alliance_name": item.get("alliance_name"),
                    "type": item.get("type") or corp_type,
                    "recruitment_active": item.get("active", True),
                    "timezones": item.get("timezones") or "",
                    "introduction": item.get("introduction") or "",
                    "biography": item.get("biography") or "",
                    "requirements": item.get("requirements") or "",
                    "member_count": len(item.get("members") or []),
                }
            )
        corps[corp_type] = rows
    return corps


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch alliance corporation profiles")
    add_base_args(parser)
    args = parser.parse_args()
    config = load_config_from_args(args)

    corps = fetch_corporations(config, args.user_agent)
    alliance = alliance_name_from_corps(corps)
    total = sum(len(rows) for rows in corps.values())

    payload = {
        "script": "fetch_corporations",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "alliance_name": alliance,
        "corps": corps,
        "summary": f"{alliance}: {total} corporations across {len(corps)} groups",
    }
    emit(payload, args.json)


if __name__ == "__main__":
    main()
