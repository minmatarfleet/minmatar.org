from __future__ import annotations

import time
from typing import Any

import requests

from feed.constants import R2Z2_USER_AGENT

ZKILL_KILL_URL = "https://zkillboard.com/api/killID/{killmail_id}/"
ESI_KILLMAIL_URL = (
    "https://esi.evetech.net/latest/killmails/{killmail_id}/{killmail_hash}/"
)


def _headers() -> dict[str, str]:
    return {"User-Agent": R2Z2_USER_AGENT, "Accept": "application/json"}


def fetch_killmail_r2z2_payload(
    killmail_id: int,
    *,
    sleep_seconds: float = 1.1,
) -> dict[str, Any] | None:
    """Fetch full killmail via zKill metadata + ESI (R2Z2-shaped payload)."""
    response = requests.get(
        ZKILL_KILL_URL.format(killmail_id=killmail_id),
        headers=_headers(),
        timeout=60,
    )
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
    esi_response = requests.get(
        ESI_KILLMAIL_URL.format(
            killmail_id=killmail_id, killmail_hash=km_hash
        ),
        headers=_headers(),
        timeout=60,
    )
    if esi_response.status_code != 200:
        return None
    raw = esi_response.json()
    return {
        "killmail": raw,
        "hash": km_hash,
        "zkb": zkb,
        "killmail_id": killmail_id,
        "sequence_id": killmail_id,
    }
