from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

import requests
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from feed.constants import R2Z2_USER_AGENT
from feed.helpers.ingest import upsert_feed_killmail_from_raw
from feed.helpers.killmail_classify import is_npc_kill
from feed.helpers.monitored_systems import get_monitored_system_ids
from feed.models import FeedKillmail

logger = logging.getLogger(__name__)

ZKILL_MAX_PAST_SECONDS = 7 * 24 * 60 * 60
ZKILL_PAST_SECONDS_URL = (
    "https://zkillboard.com/api/kills/solarSystemID/{system_id}/"
    "pastSeconds/{past_seconds}/page/{page}/"
)
ESI_KILLMAIL_URL = (
    "https://esi.evetech.net/latest/killmails/{killmail_id}/{killmail_hash}/"
)


def _headers() -> dict[str, str]:
    return {"User-Agent": R2Z2_USER_AGENT, "Accept": "application/json"}


def _empty_stats() -> dict[str, int]:
    return {
        "systems": 0,
        "listed": 0,
        "skipped_existing": 0,
        "skipped_npc": 0,
        "skipped_time": 0,
        "inserted": 0,
        "discarded": 0,
        "errors": 0,
    }


def fetch_system_kills_past_seconds(
    solar_system_id: int,
    *,
    past_seconds: int,
    page: int = 1,
) -> list[dict]:
    url = ZKILL_PAST_SECONDS_URL.format(
        system_id=solar_system_id,
        past_seconds=past_seconds,
        page=page,
    )
    response = requests.get(url, headers=_headers(), timeout=60)
    response.raise_for_status()
    kills = response.json()
    return kills if isinstance(kills, list) else []


def fetch_esi_killmail(
    killmail_id: int,
    killmail_hash: str,
    *,
    max_attempts: int = 3,
) -> dict | None:
    url = ESI_KILLMAIL_URL.format(
        killmail_id=killmail_id,
        killmail_hash=killmail_hash,
    )
    for attempt in range(max_attempts):
        response = requests.get(url, headers=_headers(), timeout=60)
        if response.status_code == 200:
            return response.json()
        if response.status_code == 429 and attempt + 1 < max_attempts:
            time.sleep(2**attempt)
            continue
        if response.status_code in {404, 420}:
            return None
        response.raise_for_status()
    return None


def _process_backfill_entry(
    entry: dict,
    *,
    cutoff: datetime,
    allowlist: frozenset[int],
    sleep_seconds: float,
) -> str:
    killmail_id = entry.get("killmail_id")
    zkb = entry.get("zkb") or {}
    killmail_hash = zkb.get("hash")
    if not killmail_id or not killmail_hash:
        return "errors"
    if is_npc_kill(zkb):
        return "skipped_npc"
    if FeedKillmail.objects.filter(killmail_id=killmail_id).exists():
        return "skipped_existing"

    raw = fetch_esi_killmail(killmail_id, killmail_hash)
    if raw is None:
        return "errors"

    killmail_time = parse_datetime(raw.get("killmail_time", ""))
    if killmail_time is not None and killmail_time < cutoff:
        return "skipped_time"

    result = upsert_feed_killmail_from_raw(
        raw,
        zkb_meta=zkb,
        allowlist=allowlist,
    )
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    return "inserted" if result else "discarded"


def _backfill_system(
    solar_system_id: int,
    *,
    past_seconds: int,
    cutoff: datetime,
    allowlist: frozenset[int],
    stats: dict[str, int],
    sleep_seconds: float,
    max_pages_per_system: int,
) -> None:
    for page in range(1, max_pages_per_system + 1):
        try:
            entries = fetch_system_kills_past_seconds(
                solar_system_id,
                past_seconds=past_seconds,
                page=page,
            )
        except requests.RequestException as exc:
            logger.warning(
                "zKill backfill failed system=%s page=%s: %s",
                solar_system_id,
                page,
                exc,
            )
            stats["errors"] += 1
            return

        if not entries:
            return

        for entry in entries:
            stats["listed"] += 1
            outcome = _process_backfill_entry(
                entry,
                cutoff=cutoff,
                allowlist=allowlist,
                sleep_seconds=sleep_seconds,
            )
            stats[outcome] += 1


def backfill_monitored_systems(
    *,
    hours: int = 24,
    sleep_seconds: float = 0.25,
    max_pages_per_system: int = 20,
) -> dict[str, int]:
    """Pull recent zKill kills for all monitored systems and ingest via ESI."""
    if hours <= 0:
        raise ValueError("hours must be positive")

    past_seconds = min(int(hours * 3600), ZKILL_MAX_PAST_SECONDS)
    cutoff = timezone.now() - timedelta(hours=hours)
    allowlist = get_monitored_system_ids(force_refresh=True)
    if not allowlist:
        raise ValueError(
            "No active FeedMonitoredSystem rows; seed systems first"
        )

    stats = _empty_stats()
    for solar_system_id in sorted(allowlist):
        stats["systems"] += 1
        _backfill_system(
            solar_system_id,
            past_seconds=past_seconds,
            cutoff=cutoff,
            allowlist=allowlist,
            stats=stats,
            sleep_seconds=sleep_seconds,
            max_pages_per_system=max_pages_per_system,
        )
    return stats
