#!/usr/bin/env python3
"""Match recruitment ad URLs to corporation names (mechanical string match)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scout_lib import emit  # noqa: E402


def corp_search_terms(corp_name: str) -> list[str]:
    name_l = corp_name.lower().strip()
    terms = [name_l]
    if name_l.startswith("the "):
        terms.append(name_l[4:])
    first_word = name_l.split()[0]
    if len(first_word) >= 5 and first_word not in ("minmatar", "administrative"):
        terms.append(first_word)
    return terms


def map_corp_ads(ads: list[dict], corps: dict[str, list[dict]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for rows in corps.values():
        for corp in rows:
            name = corp["name"]
            for ad in ads:
                title_l = ad["title"].lower()
                if any(term in title_l for term in corp_search_terms(name)):
                    mapping.setdefault(name, ad["url"])
                    break
    return mapping


def load_json_arg(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Match recruitment ads to corps by name in ad titles"
    )
    parser.add_argument(
        "--corporations",
        required=True,
        help="JSON from fetch_corporations.py (file path)",
    )
    parser.add_argument(
        "--ads",
        required=True,
        help="JSON from fetch_recruitment_ads.py (file path)",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    corps_payload = load_json_arg(args.corporations)
    ads_payload = load_json_arg(args.ads)

    corps = corps_payload.get("corps", corps_payload)
    ads = ads_payload.get("ads", ads_payload)
    corp_ads = map_corp_ads(ads, corps)

    payload = {
        "script": "match_corp_ads",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corp_ads": corp_ads,
        "summary": f"Matched {len(corp_ads)} corps to recruitment ads",
    }
    emit(payload, args.json)


if __name__ == "__main__":
    main()
