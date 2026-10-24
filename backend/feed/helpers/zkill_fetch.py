from __future__ import annotations

import time
from typing import Any

import requests

from feed.helpers.zkill_client import (
    ZKILL_API_BASE,
    fetch_esi_killmail,
    zkill_get,
)

ZKILL_KILL_URL = ZKILL_API_BASE + "/killID/{killmail_id}/"


def fetch_killmail_r2z2_payload(
    killmail_id: int,
    *,
    sleep_seconds: float = 1.1,
) -> dict[str, Any] | None:
    """Fetch full killmail via zKill metadata + ESI (R2Z2-shaped payload)."""
    response = zkill_get(ZKILL_KILL_URL.format(killmail_id=killmail_id))
    if response.status_code != 200:
        return None
    entries = response.json()
    if not entries:
        return None
    meta = entries[0]
    zkb = meta.get("zkb") or {}
    km_hash = meta.get("hash") or zkb.get("hash")
    if not km_hash:
        return None

    time.sleep(sleep_seconds)
    try:
        raw = fetch_esi_killmail(killmail_id, km_hash)
    except (requests.RequestException, ValueError):
        return None
    if raw is None:
        return None
    return {
        "killmail": raw,
        "hash": km_hash,
        "zkb": zkb,
        "killmail_id": killmail_id,
        "sequence_id": killmail_id,
    }
