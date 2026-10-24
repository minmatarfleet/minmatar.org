"""Resolve LP destination corporation names to ids for their logos.

Destinations are typed names (``Tungsten Corporation``), so the buyback
pages need an id to show the corporation's logo. Known corporations come
from our own table and the cache. Names neither knows are resolved by a
Celery task (one ESI call), so a page never waits on ESI: the logo shows
up on the next load. The set of destinations is small.
"""

from __future__ import annotations

import hashlib
import logging

from django.core.cache import cache
from django.db.models.functions import Lower

from eveonline.client import EsiClient
from eveonline.models import EveCorporation

logger = logging.getLogger(__name__)

CACHE_PREFIX = "lp-corp-id:"
FOUND_TTL = 30 * 24 * 3600
# Names ESI doesn't know (typos, characters) are retried daily.
MISSING_TTL = 24 * 3600
_MISSING = 0
# One queued lookup per set of names at a time.
QUEUE_LOCK_TTL = 300


def _key(name: str) -> str:
    # Names have spaces; hash them so the key is safe for any backend.
    return CACHE_PREFIX + hashlib.sha256(name.encode()).hexdigest()


def _from_esi(names: list[str]) -> dict[str, int] | None:
    response = EsiClient(None).resolve_universe_ids(names)
    if not response.success():
        return None
    found = {}
    for row in (response.results() or {}).get("corporations") or []:
        found[row["name"].lower()] = int(row["id"])
    return found


def corporation_ids(names) -> dict[str, int]:
    """Lower-cased name -> corporation id, for the names we can resolve."""
    wanted = {str(n).strip().lower() for n in names if n and str(n).strip()}
    if not wanted:
        return {}

    resolved: dict[str, int] = {}
    cached = cache.get_many([_key(n) for n in wanted])
    for name in wanted:
        value = cached.get(_key(name))
        if value is not None:
            if value != _MISSING:
                resolved[name] = value
    pending = [n for n in wanted if _key(n) not in cached]
    if not pending:
        return resolved

    for name, corporation_id in (
        EveCorporation.objects.annotate(lname=Lower("name"))
        .filter(lname__in=pending)
        .values_list("lname", "corporation_id")
    ):
        resolved[name] = int(corporation_id)
        cache.set(_key(name), int(corporation_id), FOUND_TTL)
    pending = [n for n in pending if n not in resolved]
    if not pending:
        return resolved

    _queue_esi_lookup(pending)
    return resolved


def _queue_esi_lookup(names: list[str]) -> None:
    names = sorted(names)
    # Queue dedupe, not a lock: never released, it lapses after
    # QUEUE_LOCK_TTL (see app.locks).
    lock = CACHE_PREFIX + "queued:" + _key("|".join(names))
    if not cache.add(lock, 1, QUEUE_LOCK_TTL):
        return
    # pylint: disable=import-outside-toplevel
    from industry.tasks import resolve_lp_corporation_ids_task

    try:
        resolve_lp_corporation_ids_task.delay(names)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Could not queue LP destination lookup")


def resolve_from_esi(names: list[str]) -> dict[str, int]:
    """Look ``names`` up on ESI and cache hits and misses (Celery task)."""
    try:
        from_esi = _from_esi(names)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("ESI name lookup failed for LP destinations")
        return {}
    if from_esi is None:
        return {}
    for name in names:
        corporation_id = from_esi.get(name)
        cache.set(
            _key(name),
            corporation_id or _MISSING,
            FOUND_TTL if corporation_id else MISSING_TTL,
        )
    return {n: i for n, i in from_esi.items() if n in names}
