from __future__ import annotations

from typing import Iterable

from eveonline.client import EsiClient
from eveonline.models import EveCharacter
from eveuniverse.models import EveType

from feed.models import FeedCharacterAffiliation

CAPSULE_GROUP_NAME = "Capsule"
KNOWN_CAPSULE_TYPE_IDS = frozenset({670})

_HULL_CLASS_PLURALS = {
    "Frigate": "frigates",
    "Destroyer": "destroyers",
    "Cruiser": "cruisers",
    "Battlecruiser": "battlecruisers",
    "Battleship": "battleships",
    "Capital Ship": "capital ships",
    "Industrial": "industrials",
    "Shuttle": "shuttles",
    "Freighter": "freighters",
    "Carrier": "carriers",
    "Dreadnought": "dreadnoughts",
    "Supercarrier": "supercarriers",
    "Titan": "titans",
}


def _pluralize_hull_class(group_name: str) -> str:
    return _HULL_CLASS_PLURALS.get(
        group_name,
        f"{group_name.strip().lower()}s",
    )


def _join_natural_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _chunks(items: list[int], size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def resolve_type_names(type_ids: Iterable[int]) -> dict[int, str]:
    ids = {int(type_id) for type_id in type_ids if type_id}
    if not ids:
        return {}

    names = {
        row[0]: row[1]
        for row in EveType.objects.filter(id__in=ids).values_list("id", "name")
    }
    for type_id in ids:
        names.setdefault(type_id, f"Type {type_id}")
    return names


def resolve_character_names(character_ids: Iterable[int]) -> dict[int, str]:
    ids = {int(character_id) for character_id in character_ids if character_id}
    if not ids:
        return {}

    names = {
        row[0]: row[1]
        for row in EveCharacter.objects.filter(
            character_id__in=ids
        ).values_list("character_id", "character_name")
        if row[1]
    }
    missing = ids - names.keys()
    if missing:
        names.update(_resolve_universe_names_via_esi(missing))
    return names


def _resolve_universe_names_via_esi(ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}

    client = EsiClient(None)
    names: dict[int, str] = {}
    for chunk in _chunks(sorted(ids), 1000):
        response = client.resolve_universe_names(chunk)
        if response.success():
            for row in response.results():
                names[row["id"]] = row["name"]
    for entity_id in ids:
        names.setdefault(entity_id, f"Pilot {entity_id}")
    return names


def _capsule_type_ids(type_ids: Iterable[int]) -> set[int]:
    ids = {int(type_id) for type_id in type_ids if type_id}
    if not ids:
        return set()
    capsule_ids = set(
        EveType.objects.filter(
            id__in=ids,
            eve_group__name=CAPSULE_GROUP_NAME,
        ).values_list("id", flat=True)
    )
    capsule_ids.update(KNOWN_CAPSULE_TYPE_IDS & ids)
    return capsule_ids


def without_capsule_ship_counts(
    ship_counts: dict[str, int] | None,
) -> dict[str, int]:
    if not ship_counts:
        return {}
    parsed: dict[int, int] = {}
    for key, count in ship_counts.items():
        try:
            parsed[int(key)] = count
        except (TypeError, ValueError):
            continue
    capsule_ids = _capsule_type_ids(parsed.keys())
    return {
        str(type_id): loss_count
        for type_id, loss_count in parsed.items()
        if type_id not in capsule_ids
    }


def top_ships_from_counts(
    ship_counts: dict[str, int] | None,
    *,
    limit: int = 5,
) -> list[dict[str, int | str]]:
    filtered_counts = without_capsule_ship_counts(ship_counts)
    if not filtered_counts:
        return []
    sorted_rows = sorted(filtered_counts.items(), key=lambda row: -row[1])[
        :limit
    ]
    parsed_rows: list[tuple[int, int]] = []
    for key, count in sorted_rows:
        try:
            parsed_rows.append((int(key), count))
        except (TypeError, ValueError):
            continue
    names = resolve_type_names(row[0] for row in parsed_rows)
    return [
        {
            "type_id": type_id,
            "name": names.get(type_id, f"Type {type_id}"),
            "count": count,
        }
        for type_id, count in parsed_rows
    ]


def format_top_ships_phrase(
    ships: list[dict[str, int | str]], *, limit: int = 3
) -> str:
    parts: list[str] = []
    for ship in ships[:limit]:
        name = str(ship["name"])
        count = int(ship["count"])
        if count > 1:
            parts.append(f"{name} ×{count}")
        else:
            parts.append(name)
    return ", ".join(parts)


def top_hull_classes_from_counts(
    ship_counts: dict[str, int] | None,
    *,
    limit: int = 3,
) -> list[str]:
    filtered_counts = without_capsule_ship_counts(ship_counts)
    if not filtered_counts:
        return []

    type_ids: list[int] = []
    for key in filtered_counts:
        try:
            type_ids.append(int(key))
        except (TypeError, ValueError):
            continue
    if not type_ids:
        return []

    group_by_type = {
        row[0]: row[1]
        for row in EveType.objects.filter(id__in=type_ids)
        .select_related("eve_group")
        .values_list("id", "eve_group__name")
        if row[1]
    }

    class_counts: dict[str, int] = {}
    for key, count in filtered_counts.items():
        try:
            type_id = int(key)
        except (TypeError, ValueError):
            continue
        group_name = group_by_type.get(type_id)
        if not group_name or group_name == CAPSULE_GROUP_NAME:
            continue
        label = _pluralize_hull_class(group_name)
        class_counts[label] = class_counts.get(label, 0) + count

    ranked = sorted(class_counts.items(), key=lambda row: -row[1])
    return [row[0] for row in ranked[:limit]]


def format_hull_classes_phrase(
    ship_counts: dict[str, int] | None,
    *,
    limit: int = 3,
) -> str:
    return _join_natural_list(
        top_hull_classes_from_counts(ship_counts, limit=limit)
    )


def sample_fleet_roster(
    attacker_ids: list[int] | None,
    *,
    faction_id: int | None = None,
    limit: int = 8,
) -> tuple[list[dict[str, int | str]], int]:
    ids = list(attacker_ids or [])
    total = len(ids)
    if not ids:
        return [], 0

    sample: list[int] = []
    if faction_id:
        enlisted = set(
            FeedCharacterAffiliation.objects.filter(
                character_id__in=ids,
                faction_id=faction_id,
            ).values_list("character_id", flat=True)
        )
        for character_id in ids:
            if character_id in enlisted:
                sample.append(character_id)
            if len(sample) >= limit:
                break

    if len(sample) < limit:
        seen = set(sample)
        for character_id in ids:
            if character_id not in seen:
                sample.append(character_id)
            if len(sample) >= limit:
                break

    names = resolve_character_names(sample)
    roster = [
        {
            "character_id": character_id,
            "name": names.get(character_id, f"Pilot {character_id}"),
        }
        for character_id in sample
    ]
    return roster, total
