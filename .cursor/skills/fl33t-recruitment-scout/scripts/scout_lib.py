"""Shared helpers for recruitment scout data scripts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

DEFAULT_USER_AGENT = "eve-alliance-recruitment-scout/1.0"
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.json"


def default_config_path() -> str:
    return str(DEFAULT_CONFIG)


def load_config(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def reddit_headers(user_agent: str, token: str | None = None) -> dict[str, str]:
    headers = {"User-Agent": user_agent}
    if token:
        headers["Authorization"] = f"bearer {token}"
    return headers


def get_reddit_token(user_agent: str) -> str | None:
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    secret = os.environ.get("REDDIT_SECRET")
    username = os.environ.get("REDDIT_USERNAME")
    password = os.environ.get("REDDIT_PASSWORD")
    if not all([client_id, secret, username, password]):
        return None

    auth = requests.auth.HTTPBasicAuth(client_id, secret)
    resp = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=auth,
        headers=reddit_headers(user_agent),
        data={
            "grant_type": "password",
            "username": username,
            "password": password,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def cutoff_from_days(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return
    print(payload.get("summary", "(use --json for full output)"))


def add_base_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        default=default_config_path(),
        help="Path to config.json",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)


def load_config_from_args(args: argparse.Namespace) -> dict[str, Any]:
    if not os.path.isfile(args.config):
        print(f"Config not found: {args.config}", file=sys.stderr)
        sys.exit(1)
    return load_config(args.config)


def alliance_name_from_corps(corps: dict[str, list[dict]]) -> str:
    for rows in corps.values():
        for corp in rows:
            if corp.get("alliance_name"):
                return corp["alliance_name"]
    return "Alliance"
