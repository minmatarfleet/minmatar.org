"""Resolve a pasted Local member list into militia, alliance and standing.

Three bulk ESI calls at most (names -> ids, ids -> affiliation, alliance
ids -> names), each cached per entity so the same pilots sitting in Local
across many pastes cost nothing after the first. The desktop preview runs
this on every paste, so a Share right after costs nothing either.

When ESI can't answer (down, or the app is close to ESI's error limit),
affiliations come from the killmail feed's own table instead, which knows
most pilots who fight in the warzone. Without names -> ids there is
nothing to look up: the report keeps the pilot count and
``resolved: false``.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Callable, Iterable

from django.core.cache import cache

from campaigns.services import esi_gate
from eveonline.client import EsiClient
from eveonline.constants import MINMATAR_FLEET_ALLIANCE_ID
from feed.models import FeedCharacterAffiliation

logger = logging.getLogger(__name__)

AMARR_FACTION_ID = 500003
MINMATAR_FACTION_ID = 500002

HOSTILE = "hostile"
NEUTRAL = "neutral"
FRIENDLY = "friendly"

NAME_TTL = 7 * 24 * 3600  # character names never move to another id
AFFILIATION_TTL = 3600  # ESI caches affiliation for an hour
ENTITY_NAME_TTL = 24 * 3600

IDS_CHUNK = 500
AFFILIATION_CHUNK = 1000
NAMES_CHUNK = 1000
MAX_ALLIANCE_ROWS = 25

_MISSING = 0  # cached for names ESI doesn't know, so they aren't retried


def _chunks(items: list, size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _esi_ids(names: list[str]) -> dict[str, int] | None:
    found: dict[str, int] = {}
    client = EsiClient(None)
    for chunk in _chunks(names, IDS_CHUNK):
        response = client.resolve_universe_ids(chunk)
        if not response.success():
            return None
        for row in (response.results() or {}).get("characters") or []:
            found[row["name"].lower()] = int(row["id"])
    return found


def _esi_affiliations(ids: list[int]) -> dict[int, dict] | None:
    found: dict[int, dict] = {}
    client = EsiClient(None)
    for chunk in _chunks(ids, AFFILIATION_CHUNK):
        response = client.get_character_affiliations(chunk)
        if not response.success():
            return None
        for row in response.results() or []:
            found[int(row["character_id"])] = {
                "corporation_id": row.get("corporation_id"),
                "alliance_id": row.get("alliance_id"),
                "faction_id": row.get("faction_id"),
            }
    return found


def _esi_names(ids: list[int]) -> dict[int, str] | None:
    found: dict[int, str] = {}
    client = EsiClient(None)
    for chunk in _chunks(ids, NAMES_CHUNK):
        response = client.resolve_universe_names(chunk)
        if not response.success():
            return None
        for row in response.results() or []:
            found[int(row["id"])] = row["name"]
    return found


def _feed_affiliations(ids: list[int]) -> dict[int, dict]:
    """Affiliations the killmail feed confirmed with ESI (refreshed weekly).

    The feed only keeps militia factions, which is all a standing needs.
    """
    rows = FeedCharacterAffiliation.objects.filter(
        character_id__in=ids, esi_checked_at__isnull=False
    ).values_list(
        "character_id", "corporation_id", "alliance_id", "faction_id"
    )
    return {
        int(character_id): {
            "corporation_id": corporation_id,
            "alliance_id": alliance_id,
            "faction_id": faction_id,
        }
        for character_id, corporation_id, alliance_id, faction_id in rows
    }


def esi_available() -> bool:
    """False while ESI is error-limiting us, or close to it.

    Successful calls don't count against ESI's app-wide error limit, but
    every Local paste would add to a storm of errors during an outage.
    """
    return (
        esi_gate.pause_remaining() == 0
        and esi_gate.error_budget() > esi_gate.ERROR_BUDGET_FLOOR
    )


def _cached_lookup(
    keys: Iterable,
    prefix: str,
    fetch: Callable[[list], dict | None],
    ttl: int,
    *,
    missing=None,
    fallback: Callable[[list], dict] | None = None,
) -> dict | None:
    """cache.get_many, fetch the rest in bulk, cache.set_many them.

    When the fetch fails, ``fallback`` fills in what it can, uncached, so
    ESI's answer replaces it as soon as ESI is back.
    """
    keys = list(dict.fromkeys(keys))
    # Names have spaces; keep cache keys to one token.
    cache_keys = {key: f"{prefix}{key}".replace(" ", "_") for key in keys}
    cached = cache.get_many(list(cache_keys.values()))
    found = {key: cached[ck] for key, ck in cache_keys.items() if ck in cached}
    todo = [key for key in keys if key not in found]
    if todo:
        fetched = fetch(todo)
        if fetched is None:
            if fallback is None:
                return None
            found.update(fallback(todo))
            return found
        to_cache = {}
        for key in todo:
            value = fetched.get(key, missing)
            if value is None:
                continue
            found[key] = value
            to_cache[cache_keys[key]] = value
        cache.set_many(to_cache, ttl)
    return found


def standing(affiliation: dict) -> str:
    if affiliation.get("alliance_id") == MINMATAR_FLEET_ALLIANCE_ID:
        return FRIENDLY
    if affiliation.get("faction_id") == MINMATAR_FACTION_ID:
        return FRIENDLY
    if affiliation.get("faction_id") == AMARR_FACTION_ID:
        return HOSTILE
    return NEUTRAL


def _no_esi(keys: list) -> None:
    """Stands in for an ESI fetch that isn't allowed: only cached keys."""
    return None


def summarize_local(names: list[str], *, use_esi: bool = True) -> dict:
    summary = {
        "pilots": len(names),
        "resolved": False,
        "unknown": 0,
        "standings": {HOSTILE: 0, NEUTRAL: 0, FRIENDLY: 0},
        "militia": {"amarr": 0, "minmatar": 0, "none": 0},
        "alliances": [],
    }
    use_esi = use_esi and esi_available()
    ids_by_name = _cached_lookup(
        (name.lower() for name in names),
        "intel:charid:",
        _esi_ids if use_esi else _no_esi,
        NAME_TTL,
        missing=_MISSING,
    )
    if ids_by_name is None:
        return summary
    character_ids = [cid for cid in ids_by_name.values() if cid]
    affiliations = _cached_lookup(
        character_ids,
        "intel:aff:",
        _esi_affiliations if use_esi else _no_esi,
        AFFILIATION_TTL,
        fallback=_feed_affiliations,
    )
    if character_ids and not affiliations:
        return summary

    alliance_counts: Counter = Counter()
    alliance_standing: dict[int | None, str] = {}
    for character_id in character_ids:
        affiliation = affiliations.get(character_id)
        if not affiliation:
            continue
        side = standing(affiliation)
        summary["standings"][side] += 1
        faction_id = affiliation.get("faction_id")
        militia = (
            "amarr"
            if faction_id == AMARR_FACTION_ID
            else "minmatar" if faction_id == MINMATAR_FACTION_ID else "none"
        )
        summary["militia"][militia] += 1
        alliance_id = affiliation.get("alliance_id")
        alliance_counts[alliance_id] += 1
        # An alliance is as hostile as its most hostile pilot here.
        if alliance_standing.get(alliance_id) != HOSTILE:
            alliance_standing[alliance_id] = side

    alliance_ids = [aid for aid in alliance_counts if aid]
    alliance_names = (
        _cached_lookup(
            alliance_ids,
            "intel:entity:",
            _esi_names if use_esi else _no_esi,
            ENTITY_NAME_TTL,
        )
        or {}
    )
    rows = [
        {
            "id": alliance_id,
            "name": (
                alliance_names.get(alliance_id, f"Alliance {alliance_id}")
                if alliance_id
                else "No alliance"
            ),
            "count": count,
            "standing": alliance_standing.get(alliance_id, NEUTRAL),
        }
        for alliance_id, count in alliance_counts.items()
    ]
    rows.sort(key=lambda row: (-row["count"], row["name"]))
    resolved = sum(alliance_counts.values())
    summary.update(
        {
            "resolved": True,
            "unknown": len(names) - resolved,
            "alliances": rows[:MAX_ALLIANCE_ROWS],
        }
    )
    return summary
