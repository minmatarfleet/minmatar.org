from __future__ import annotations

import logging
import time
from typing import Any

import requests

from feed.constants import (
    R2Z2_BANNED_SLEEP_SECONDS,
    R2Z2_NOT_FOUND_SLEEP_MS,
    R2Z2_POLL_SOFT_TIME_LIMIT_SECONDS,
    R2Z2_RATE_LIMIT_SLEEP_SECONDS,
    R2Z2_SEQUENCE_URL,
    R2Z2_SUCCESS_SLEEP_MS,
    R2Z2_USER_AGENT,
)
from feed.helpers.ingest import upsert_feed_killmail_from_r2z2
from feed.helpers.capital_pings import maybe_notify_capital_kill
from feed.helpers.monitored_systems import get_monitored_system_ids
from feed.models import FeedR2z2Cursor

logger = logging.getLogger(__name__)

R2Z2_BASE = "https://r2z2.zkillboard.com/ephemeral"


def _headers() -> dict[str, str]:
    return {"User-Agent": R2Z2_USER_AGENT, "Accept": "application/json"}


def _retry_after_seconds(
    response: requests.Response,
    *,
    default_seconds: float,
) -> float:
    retry_after = response.headers.get("Retry-After")
    if not retry_after:
        return default_seconds
    try:
        return max(float(retry_after), default_seconds)
    except ValueError:
        return default_seconds


def fetch_latest_sequence() -> int:
    response = requests.get(R2Z2_SEQUENCE_URL, headers=_headers(), timeout=30)
    if response.status_code == 429:
        sleep_seconds = _retry_after_seconds(
            response, default_seconds=float(R2Z2_RATE_LIMIT_SLEEP_SECONDS)
        )
        logger.warning(
            "R2Z2 sequence fetch rate limited; sleeping %.0fs", sleep_seconds
        )
        time.sleep(sleep_seconds)
        response = requests.get(
            R2Z2_SEQUENCE_URL, headers=_headers(), timeout=30
        )
    if response.status_code == 403:
        logger.warning(
            "R2Z2 sequence fetch forbidden; sleeping %.0fs (likely IP ban)",
            R2Z2_BANNED_SLEEP_SECONDS,
        )
        time.sleep(R2Z2_BANNED_SLEEP_SECONDS)
        response = requests.get(
            R2Z2_SEQUENCE_URL, headers=_headers(), timeout=30
        )
    response.raise_for_status()
    data = response.json()
    return int(data["sequence"])


def fetch_sequence_payload(
    sequence_id: int,
) -> tuple[int, dict[str, Any] | None, float | None]:
    url = f"{R2Z2_BASE}/{sequence_id}.json"
    response = requests.get(url, headers=_headers(), timeout=30)
    if response.status_code == 404:
        return 404, None, None
    if response.status_code == 429:
        return (
            429,
            None,
            _retry_after_seconds(
                response, default_seconds=float(R2Z2_RATE_LIMIT_SLEEP_SECONDS)
            ),
        )
    if response.status_code == 403:
        return 403, None, float(R2Z2_BANNED_SLEEP_SECONDS)
    response.raise_for_status()
    return 200, response.json(), None


def poll_r2z2_batch(*, max_seconds: float | None = None) -> dict[str, int]:
    """Poll R2Z2 until caught up, idle (404), throttled, or time budget exhausted.

    Follows zKillboard R2Z2 guidance: 100ms between successful fetches when
    catching up, >= 6s after 404 at the live edge, and long backoff on 429/403.
    """
    budget = max_seconds or R2Z2_POLL_SOFT_TIME_LIMIT_SECONDS
    started = time.monotonic()
    cursor = FeedR2z2Cursor.get_singleton()
    sequence = cursor.last_sequence_id + 1 if cursor.last_sequence_id else 0

    if sequence <= 0:
        sequence = fetch_latest_sequence()

    allowlist = get_monitored_system_ids()
    stats = {
        "processed": 0,
        "inserted": 0,
        "discarded": 0,
        "errors": 0,
        "rate_limited": 0,
        "banned": 0,
        "capital_pings": 0,
    }

    while (time.monotonic() - started) < budget:
        try:
            status, payload, retry_after = fetch_sequence_payload(sequence)
        except requests.RequestException as exc:
            logger.warning(
                "R2Z2 fetch error at sequence %s: %s", sequence, exc
            )
            stats["errors"] += 1
            time.sleep(R2Z2_NOT_FOUND_SLEEP_MS / 1000)
            break

        if status == 429:
            sleep_seconds = retry_after or float(R2Z2_RATE_LIMIT_SLEEP_SECONDS)
            stats["rate_limited"] += 1
            logger.warning(
                "R2Z2 rate limited at sequence %s; sleeping %.0fs",
                sequence,
                sleep_seconds,
            )
            time.sleep(sleep_seconds)
            break

        if status == 403:
            sleep_seconds = retry_after or float(R2Z2_BANNED_SLEEP_SECONDS)
            stats["banned"] += 1
            logger.warning(
                "R2Z2 access forbidden at sequence %s; sleeping %.0fs",
                sequence,
                sleep_seconds,
            )
            time.sleep(sleep_seconds)
            break

        if status == 404:
            time.sleep(R2Z2_NOT_FOUND_SLEEP_MS / 1000)
            break

        stats["processed"] += 1
        if payload:
            try:
                if maybe_notify_capital_kill(payload):
                    stats["capital_pings"] += 1
            except Exception:
                logger.exception(
                    "Capital ping evaluation failed at sequence %s", sequence
                )
            result = upsert_feed_killmail_from_r2z2(
                payload, allowlist=allowlist
            )
            if result:
                stats["inserted"] += 1
            else:
                stats["discarded"] += 1

        sequence += 1
        cursor.last_sequence_id = sequence - 1
        cursor.save(update_fields=["last_sequence_id", "updated_at"])
        time.sleep(R2Z2_SUCCESS_SLEEP_MS / 1000)

    return stats
