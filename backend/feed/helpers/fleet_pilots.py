"""Pilots in a tracked fleet, so the feed keeps their killmails anywhere.

The feed normally keeps only killmails in monitored systems. A fleet that
roams out of the warzone would lose those fights, so a killmail is also kept
when its victim or any attacker was seen in a tracked fleet recently.

"Recently" covers the fleet's settle window: zKill can deliver a killmail
well after the ship died, and the fleet's fight timeline keeps rebuilding
until then. The set is a superset; matching a killmail to a fleet still
checks that the pilot was in fleet at that moment.
"""

from __future__ import annotations

import threading
import time
from datetime import timedelta
from typing import Any

from django.utils import timezone

# The fight timeline settles 2 hours after a fleet ends; keep a margin.
FLEET_PILOT_WINDOW = timedelta(hours=2, minutes=30)
# The fleet poller runs every 30 seconds; a pilot who joined since the last
# refresh is picked up on the next one.
CACHE_TTL_SECONDS = 30

_lock = threading.Lock()
_cached: frozenset[int] | None = None
_loaded_at = 0.0


def invalidate_fleet_pilot_cache() -> None:
    global _cached, _loaded_at
    with _lock:
        _cached = None
        _loaded_at = 0.0


def fleet_pilot_ids(*, force_refresh: bool = False) -> frozenset[int]:
    """Character ids seen in any tracked fleet in the last 2.5 hours."""
    global _cached, _loaded_at
    now = time.monotonic()
    with _lock:
        if (
            not force_refresh
            and _cached is not None
            and now - _loaded_at < CACHE_TTL_SECONDS
        ):
            return _cached

    # Imported here so the feed does not load fleets.models at import time.
    # pylint: disable=import-outside-toplevel
    from fleets.models import EveFleetInstanceMember

    ids = frozenset(
        EveFleetInstanceMember.objects.filter(
            updated_at__gte=timezone.now() - FLEET_PILOT_WINDOW
        )
        .values_list("character_id", flat=True)
        .distinct()
    )
    with _lock:
        _cached = ids
        _loaded_at = now
    return ids


def has_fleet_pilot(
    raw: dict[str, Any], pilots: frozenset[int] | None = None
) -> bool:
    """True when the victim or an attacker is a recent fleet pilot."""
    pilots = fleet_pilot_ids() if pilots is None else pilots
    if not pilots:
        return False
    victim = (raw.get("victim") or {}).get("character_id")
    if victim in pilots:
        return True
    return any(
        attacker.get("character_id") in pilots
        for attacker in raw.get("attackers") or []
    )
