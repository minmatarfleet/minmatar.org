"""Corporation and alliance lookup for structure scouting.

Known alliance rows match immediately. Anything else comes from the
authenticated ESI character search, then ``/universe/names/`` for labels.
"""

from __future__ import annotations

from django.db.models import Q

from eveonline.client import (
    CHAR_ESI_SUSPENDED,
    EsiClient,
    NO_CLIENT_CHAR,
    NO_VALID_ACCESS_TOKEN,
    NO_VALID_ESI_TOKEN,
)
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EvePlayer,
)

LIMIT = 8
MIN_QUERY = 2
_SKIP_TOKEN = {
    NO_VALID_ESI_TOKEN,
    NO_CLIENT_CHAR,
    CHAR_ESI_SUSPENDED,
    NO_VALID_ACCESS_TOKEN,
}


def search_entities(user, kind: str, query: str) -> list[dict]:
    """Return up to LIMIT matches for ``corporation`` or ``alliance``."""
    needle = (query or "").strip()
    if kind not in ("corporation", "alliance") or len(needle) < MIN_QUERY:
        return []

    found: dict[int, dict] = {}
    for row in _local_rows(kind, needle):
        entity_id = (
            row.corporation_id if kind == "corporation" else row.alliance_id
        )
        found[entity_id] = {
            "id": entity_id,
            "name": row.name,
            "ticker": row.ticker or "",
            "kind": kind,
        }

    esi_order = _esi_ids(user, kind, needle)
    missing = [entity_id for entity_id in esi_order if entity_id not in found][
        :LIMIT
    ]
    if missing:
        _fill_names(found, kind, missing)

    order = {entity_id: index for index, entity_id in enumerate(esi_order)}
    ranked = sorted(
        found.values(), key=lambda item: _sort_key(item, needle, order)
    )
    return ranked[:LIMIT]


def _local_rows(kind: str, needle: str):
    query = Q(name__icontains=needle) | Q(ticker__icontains=needle)
    if kind == "corporation":
        return EveCorporation.objects.filter(query).order_by("name")[:LIMIT]
    return EveAlliance.objects.filter(query).order_by("name")[:LIMIT]


def _search_character_ids(user) -> list[int]:
    if not getattr(user, "is_authenticated", False):
        return []
    character_ids = list(
        EveCharacter.objects.filter(user=user, esi_suspended=False)
        .exclude(token_id=None)
        .values_list("character_id", flat=True)
    )
    primary_id = (
        EvePlayer.objects.filter(user=user)
        .values_list("primary_character__character_id", flat=True)
        .first()
    )
    if primary_id in character_ids:
        character_ids.remove(primary_id)
        character_ids.insert(0, primary_id)
    return character_ids


def _esi_ids(user, kind: str, needle: str) -> list[int]:
    if len(needle) < 3:
        return []
    for character_id in _search_character_ids(user):
        result = EsiClient(character_id).search_category(kind, needle)
        if not result.success():
            if result.response_code in _SKIP_TOKEN:
                continue
            return []
        payload = result.results() or {}
        raw_ids = payload.get(kind) or []
        return [int(entity_id) for entity_id in raw_ids][:LIMIT]
    return []


def _fill_names(found: dict, kind: str, missing: list[int]):
    # /universe/names/ is public; it does not need the search token.
    named = EsiClient(None).resolve_universe_names(missing)
    if not named.success():
        return
    for row in named.results() or []:
        entity_id, name, category = _name_parts(row)
        if entity_id in missing and category == kind and name:
            found[entity_id] = {
                "id": entity_id,
                "name": name,
                "ticker": "",
                "kind": kind,
            }


def _name_parts(row):
    if isinstance(row, dict):
        return row.get("id"), row.get("name"), row.get("category")
    return (
        getattr(row, "id", None),
        getattr(row, "name", None),
        getattr(row, "category", None),
    )


def _sort_key(item: dict, needle: str, esi_order: dict[int, int]):
    name = (item["name"] or "").lower()
    ticker = (item["ticker"] or "").lower()
    query = needle.lower()
    if query in (name, ticker):
        rank = 0
    elif name.startswith(query) or ticker.startswith(query):
        rank = 1
    else:
        rank = 2
    return (rank, esi_order.get(item["id"], LIMIT + 1), name)
