"""HTTP helpers shared by the zKillboard, R2Z2 and killmail-by-hash code.

One place owns the feed's User-Agent and the R2Z2 base URL, and one function
fetches an ESI killmail by hash with one retry policy. Pacing between calls
stays with each caller: R2Z2 spacing lives on its cursor, and the backfill
and history walks pass their own ``sleep_seconds``.
"""

from __future__ import annotations

import time
from typing import Any

import requests

from eveonline.esi_http import esi_request
from feed.constants import R2Z2_BASE_URL, R2Z2_USER_AGENT

ZKILL_API_BASE = "https://zkillboard.com/api"
ESI_KILLMAIL_PATH = "/killmails/{killmail_id}/{killmail_hash}/"
ESI_KILLMAIL_ATTEMPTS = 3


def headers() -> dict[str, str]:
    """Headers zKillboard and R2Z2 ask every client to send."""
    return {"User-Agent": R2Z2_USER_AGENT, "Accept": "application/json"}


def zkill_get(
    url: str, *, params: dict | None = None, timeout: float = 60
) -> requests.Response:
    """GET a zKillboard or R2Z2 URL with the feed's headers."""
    return requests.get(url, headers=headers(), params=params, timeout=timeout)


def r2z2_sequence_url(sequence_id: int) -> str:
    return f"{R2Z2_BASE_URL}/{sequence_id}.json"


def fetch_esi_killmail(
    killmail_id: int,
    killmail_hash: str,
    *,
    max_attempts: int = ESI_KILLMAIL_ATTEMPTS,
) -> dict[str, Any] | None:
    """One killmail from ESI by id and hash.

    A 429 is retried with a short backoff. A 404 (bad hash) or 420 (error
    limit; the transport already pauses the app's ESI pollers) is None.
    Any other failure raises.
    """
    path = ESI_KILLMAIL_PATH.format(
        killmail_id=killmail_id, killmail_hash=killmail_hash
    )
    for attempt in range(max_attempts):
        result = esi_request("GET", path, timeout=60)
        if result.ok:
            return result.data
        if result.status is None or result.status < 400:
            raise result.error
        if result.status == 429 and attempt + 1 < max_attempts:
            time.sleep(2**attempt)
            continue
        if result.status in {404, 420}:
            return None
        result.response.raise_for_status()
    return None
