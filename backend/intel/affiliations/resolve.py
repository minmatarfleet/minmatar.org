"""The one lookup every tool uses to put a pilot or group in its bloc.

The whole table (anchors plus live affiliations) is small, so it is read
into one map, cached for ten minutes and dropped whenever an affiliation
or bloc changes. A cache outage reads the database instead of failing.
"""

from __future__ import annotations

import logging

from django.core.cache import cache
from django.db.models import Count, Q

from intel.models import IntelAffiliation, IntelBloc, IntelEntity

logger = logging.getLogger(__name__)

MAP_CACHE_KEY = "intel:blocs:map:v1"
MAP_CACHE_SECONDS = 600

ANCHOR = "anchor"
CONFIRMED = IntelAffiliation.Status.CONFIRMED
SUGGESTED = IntelAffiliation.Status.SUGGESTED


def _key(kind: str, eve_id: int) -> str:
    return f"{kind}:{int(eve_id)}"


def _entry(bloc_id, bloc_name, relation, status, confidence) -> dict:
    return {
        "id": bloc_id,
        "name": bloc_name,
        "relation": relation,
        "status": status,
        "confidence": round(float(confidence), 2),
    }


def _better(new: dict, old: dict | None) -> bool:
    if old is None:
        return True
    rank = {ANCHOR: 2, CONFIRMED: 1, SUGGESTED: 0}
    return (rank[new["status"]], new["confidence"]) > (
        rank[old["status"]],
        old["confidence"],
    )


def build_map() -> dict[str, dict]:
    """``"<kind>:<eve_id>" -> bloc entry`` for every live affiliation."""
    found: dict[str, dict] = {}
    live = Q(
        affiliations__status__in=[CONFIRMED, SUGGESTED],
        affiliations__ended=False,
    )
    anchors = (
        IntelBloc.objects.filter(anchor__isnull=False)
        .annotate(live=Count("affiliations", filter=live))
        .filter(Q(manual=True) | Q(live__gt=0))
    )
    for bloc_id, name, kind, eve_id in anchors.values_list(
        "id", "name", "anchor__kind", "anchor__eve_id"
    ):
        found[_key(kind, eve_id)] = _entry(bloc_id, name, ANCHOR, ANCHOR, 1)
    rows = IntelAffiliation.objects.filter(
        status__in=[CONFIRMED, SUGGESTED], ended=False
    ).values_list(
        "bloc_id",
        "bloc__name",
        "entity__kind",
        "entity__eve_id",
        "relation",
        "status",
        "confidence",
    )
    for bloc_id, name, kind, eve_id, relation, status, confidence in rows:
        key = _key(kind, eve_id)
        entry = _entry(bloc_id, name, relation, status, confidence)
        if _better(entry, found.get(key)):
            found[key] = entry
    return found


def bloc_map() -> dict[str, dict]:
    try:
        cached = cache.get(MAP_CACHE_KEY)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Bloc map cache unavailable", exc_info=True)
        return build_map()
    if cached is not None:
        return cached
    found = build_map()
    try:
        cache.set(MAP_CACHE_KEY, found, MAP_CACHE_SECONDS)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Bloc map cache unavailable", exc_info=True)
    return found


def invalidate() -> None:
    try:
        cache.delete(MAP_CACHE_KEY)
    except Exception:  # pylint: disable=broad-exception-caught
        logger.warning("Bloc map cache unavailable", exc_info=True)


def _visible(entry: dict | None, confirmed_only: bool) -> dict | None:
    if entry is None:
        return None
    if confirmed_only and entry["status"] == SUGGESTED:
        return None
    return entry


def bloc_for_group(
    kind: str,
    eve_id: int | None,
    *,
    confirmed_only: bool = False,
    blocs: dict | None = None,
) -> dict | None:
    """The bloc an alliance or corporation belongs to, if any."""
    if not eve_id:
        return None
    blocs = bloc_map() if blocs is None else blocs
    return _visible(blocs.get(_key(kind, eve_id)), confirmed_only)


def bloc_for(
    *,
    character_id: int | None = None,
    corporation_id: int | None = None,
    alliance_id: int | None = None,
    confirmed_only: bool = False,
    blocs: dict | None = None,
) -> dict | None:
    """A pilot's bloc: their own affiliation, else their corp's, else their
    alliance's. Pass ``blocs`` (from ``bloc_map``) when resolving many."""
    blocs = bloc_map() if blocs is None else blocs
    for kind, eve_id in (
        (IntelEntity.Kind.CHARACTER, character_id),
        (IntelEntity.Kind.CORPORATION, corporation_id),
        (IntelEntity.Kind.ALLIANCE, alliance_id),
    ):
        entry = bloc_for_group(
            kind, eve_id, confirmed_only=confirmed_only, blocs=blocs
        )
        if entry is not None:
            return entry
    return None


def public_entry(entry: dict | None) -> dict | None:
    """What a tool shows: the bloc and whether it is still only likely."""
    if entry is None:
        return None
    return {
        "id": entry["id"],
        "name": entry["name"],
        "likely": entry["status"] == SUGGESTED,
    }
