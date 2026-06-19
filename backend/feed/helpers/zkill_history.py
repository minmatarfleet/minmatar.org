from __future__ import annotations

import logging
from datetime import timedelta

import requests
from django.utils.dateparse import parse_datetime

from feed.constants import R2Z2_USER_AGENT
from feed.helpers.ingest import upsert_feed_killmail_from_raw
from feed.helpers.monitored_systems import get_monitored_system_ids
from feed.models import FeedKillmail

logger = logging.getLogger(__name__)

ZKILL_API = "https://zkillboard.com/api/kills/solarSystemID/{system_id}/"


def _headers() -> dict[str, str]:
    return {"User-Agent": R2Z2_USER_AGENT, "Accept": "application/json"}


def fetch_system_kills(
    solar_system_id: int,
    *,
    page: int = 1,
) -> list[dict]:
    url = ZKILL_API.format(system_id=solar_system_id)
    params = {"page": page, "w-space": 0}
    response = requests.get(url, headers=_headers(), params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def backfill_engagement(
    anchor_killmail_id: int,
    *,
    window_minutes: int = 30,
) -> dict[str, int]:
    anchor = FeedKillmail.objects.filter(
        killmail_id=anchor_killmail_id
    ).first()
    if anchor is None:
        raise ValueError(
            f"Anchor killmail {anchor_killmail_id} not in FeedKillmail"
        )

    allowlist = get_monitored_system_ids()
    system_id = anchor.solar_system_id
    window_start = anchor.killmail_time - timedelta(minutes=window_minutes)
    window_end = anchor.killmail_time + timedelta(minutes=window_minutes)

    stats = {"fetched": 0, "inserted": 0, "discarded": 0}
    for page in range(1, 6):
        try:
            kills = fetch_system_kills(system_id, page=page)
        except requests.RequestException as exc:
            logger.warning("zKill history fetch failed page %s: %s", page, exc)
            break
        if not kills:
            break
        for entry in kills:
            stats["fetched"] += 1
            killmail_id = entry.get("killmail_id")
            killmail_hash = entry.get("hash")
            zkb = entry.get("zkb") or {}
            killmail_time = entry.get("killmail_time")
            if killmail_time:
                parsed_time = parse_datetime(killmail_time)
            else:
                parsed_time = None

            if parsed_time and (
                parsed_time < window_start or parsed_time > window_end
            ):
                stats["discarded"] += 1
                continue

            raw = {
                "killmail_id": killmail_id,
                "killmail_time": killmail_time
                or anchor.killmail_time.isoformat(),
                "solar_system_id": system_id,
                "victim": entry.get("victim") or {},
                "attackers": entry.get("attackers") or [],
            }
            if killmail_id and killmail_hash:
                result = upsert_feed_killmail_from_raw(
                    raw,
                    zkb_meta=zkb,
                    allowlist=allowlist,
                )
                if result:
                    stats["inserted"] += 1
                else:
                    stats["discarded"] += 1
    return stats
