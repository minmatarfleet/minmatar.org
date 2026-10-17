#!/usr/bin/env python3
"""Register scout replies for click tracking, and read their click stats.

register: one call per open thread you draft for. Returns the reply's code
and its tracked links. Drafting the same thread again returns the same code.

stats: replies from the last N days with unique human visitors per link.

Needs MINMATAR_API_TOKEN: the auth_token cookie from my.minmatar.org, for a
user with the recruitment.scout feature.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scout_lib import add_base_args, emit, load_config_from_args  # noqa: E402


def api(config: dict, user_agent: str) -> tuple[str, dict]:
    token = os.environ.get("MINMATAR_API_TOKEN")
    if not token:
        sys.exit(
            "MINMATAR_API_TOKEN is not set. Draft with plain links, "
            "or set it to your my.minmatar.org auth_token cookie."
        )
    base = config["api_base_url"].rstrip("/") + "/recruitment/scout"
    headers = {"Authorization": f"Bearer {token}", "User-Agent": user_agent}
    return base, headers


def tracked_links(config: dict, link_base: str) -> dict[str, dict]:
    """target -> {"url": real URL, "tracked": redirect URL}."""
    return {
        target: {"url": url, "tracked": f"{link_base}{target}"}
        for target, url in config["tracked_links"]["targets"].items()
    }


def register(args, config: dict) -> dict:
    base, headers = api(config, args.user_agent)
    resp = requests.post(
        f"{base}/outreach",
        json={
            "surface": args.surface,
            "thread_url": args.thread,
            "prospect": args.prospect,
            "seat": args.seat,
        },
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    outreach = resp.json()
    links = tracked_links(config, outreach["link_base"])
    return {
        "script": "track_outreach",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "outreach": outreach,
        "links": links,
        "summary": "\n".join(
            [f"{outreach['code']}  {outreach['thread_url']}"]
            + [f"  {t}: {link['tracked']}" for t, link in links.items()]
        ),
    }


def stats(args, config: dict) -> dict:
    base, headers = api(config, args.user_agent)
    resp = requests.get(
        f"{base}/outreach",
        params={"days": args.days},
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    rows = resp.json()

    by_surface: dict[str, dict] = {}
    for row in rows:
        surface = by_surface.setdefault(
            row["surface"], {"replies": 0, "clicked": 0, "discord": 0}
        )
        surface["replies"] += 1
        surface["clicked"] += 1 if row["visitors"] else 0
        surface["discord"] += 1 if row["clicks"].get("discord") else 0

    lines = [
        f"{name}: {s['replies']} replies, {s['clicked']} clicked, "
        f"{s['discord']} clicked Discord"
        for name, s in sorted(by_surface.items())
    ]
    return {
        "script": "track_outreach",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days": args.days,
        "by_surface": by_surface,
        "replies": rows,
        "summary": "\n".join(lines) or f"No scout replies in {args.days} days",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    common = argparse.ArgumentParser(add_help=False)
    add_base_args(common)
    sub = parser.add_subparsers(dest="command", required=True)

    reg = sub.add_parser(
        "register", parents=[common], help="Get a code for one reply"
    )
    reg.add_argument(
        "--surface", required=True, choices=["evejobs", "eve", "forums"]
    )
    reg.add_argument("--thread", required=True, help="Pilot's thread URL")
    reg.add_argument("--prospect", default="", help="Their Reddit/forum name")
    reg.add_argument("--seat", default="", help="TDT, L3ARN, MFA, FW redirect…")

    st = sub.add_parser(
        "stats", parents=[common], help="Clicks on recent replies"
    )
    st.add_argument("--days", type=int, default=30)

    args = parser.parse_args()
    config = load_config_from_args(args)
    payload = register(args, config) if args.command == "register" else stats(
        args, config
    )
    emit(payload, args.json)


if __name__ == "__main__":
    main()
