"""Ship classes and sizes for d-scan summaries and ping hull strips.

Every hull gets a class (the "Frigate 14" heading on a d-scan report) and a
size rank so a row can lead with its biggest ships: capitals first, then
battleships, battlecruisers, cruisers, industrials, destroyers, frigates.
Within a class the specialised hulls (HACs, logistics, recons) outrank the
base T1 group, so a Zealot shows before an Omen.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from eveuniverse.models import EveType

from intel.services.fixtures import load_types
from intel.services.paste import DscanLine

SHIP_CATEGORY_ID = 6
CAPSULE_GROUP = "Capsule"

_CLASSES: list[tuple[str, tuple[str, ...]]] = [
    (
        "Capital",
        (
            "Titan",
            "Supercarrier",
            "Dreadnought",
            "Lancer Dreadnought",
            "Carrier",
            "Force Auxiliary",
            "Capital Industrial Ship",
            "Jump Freighter",
            "Freighter",
        ),
    ),
    ("Battleship", ("Marauder", "Black Ops", "Battleship")),
    (
        "Battlecruiser",
        (
            "Command Ship",
            "Industrial Command Ship",
            "Attack Battlecruiser",
            "Combat Battlecruiser",
        ),
    ),
    (
        "Cruiser",
        (
            "Strategic Cruiser",
            "Heavy Interdiction Cruiser",
            "Heavy Assault Cruiser",
            "Logistics",
            "Force Recon Ship",
            "Combat Recon Ship",
            "Flag Cruiser",
            "Cruiser",
        ),
    ),
    (
        "Industrial",
        (
            "Exhumer",
            "Mining Barge",
            "Deep Space Transport",
            "Blockade Runner",
            "Hauler",
        ),
    ),
    (
        "Destroyer",
        (
            "Command Destroyer",
            "Tactical Destroyer",
            "Interdictor",
            "Destroyer",
        ),
    ),
    (
        "Frigate",
        (
            "Assault Frigate",
            "Interceptor",
            "Electronic Attack Ship",
            "Logistics Frigate",
            "Stealth Bomber",
            "Covert Ops",
            "Expedition Frigate",
            "Prototype Exploration Ship",
            "Frigate",
        ),
    ),
    ("Shuttle", ("Corvette", "Shuttle")),
]

# group -> (class name, rank); a lower rank is a bigger ship.
_GROUP_RANK: dict[str, tuple[str, int]] = {
    group: (class_name, class_index * 100 + group_index)
    for class_index, (class_name, groups) in enumerate(_CLASSES)
    for group_index, group in enumerate(groups)
}
_CLASS_RANK = {name: index for index, (name, _) in enumerate(_CLASSES)}
UNKNOWN_SHIP_RANK = 50 * 100

_OTHER_LABELS = {
    18: "Drone",
    87: "Fighter",
    22: "Deployable",
    23: "Starbase",
    40: "Sovereignty structure",
    46: "Orbital",
    65: "Structure",
}


@dataclass(frozen=True)
class TypeInfo:
    type_id: int
    name: str
    group: str
    category_id: int | None

    @property
    def is_capsule(self) -> bool:
        return self.group == CAPSULE_GROUP

    @property
    def is_ship(self) -> bool:
        return self.category_id == SHIP_CATEGORY_ID and not self.is_capsule

    @property
    def ship_class(self) -> str:
        return _GROUP_RANK.get(self.group, ("Ship", UNKNOWN_SHIP_RANK))[0]

    @property
    def rank(self) -> int:
        return _GROUP_RANK.get(self.group, ("Ship", UNKNOWN_SHIP_RANK))[1]

    @property
    def other_label(self) -> str:
        return _OTHER_LABELS.get(self.category_id, self.group or "Other")


def type_info(
    type_ids: Iterable[int], names: dict[int, str] | None = None
) -> dict[int, TypeInfo]:
    """Classify types from the fixture; one DB query for any it lacks.

    ``names`` (from the paste) labels types neither source knows.
    """
    names = names or {}
    fixture = load_types()
    found: dict[int, TypeInfo] = {}
    missing: set[int] = set()
    for type_id in set(type_ids):
        row = fixture.get(type_id)
        if row:
            found[type_id] = TypeInfo(type_id, row[0], row[1], row[2])
        else:
            missing.add(type_id)
    if missing:
        # Hulls newer than the fixture's SDE, if eveuniverse has them.
        for type_id, name, group, category_id in EveType.objects.filter(
            id__in=missing
        ).values_list(
            "id", "name", "eve_group__name", "eve_group__eve_category_id"
        ):
            found[type_id] = TypeInfo(type_id, name, group or "", category_id)
            missing.discard(type_id)
    for type_id in missing:
        found[type_id] = TypeInfo(
            type_id, names.get(type_id) or f"Type {type_id}", "", None
        )
    return found


def hull_list(counts: dict[int, int], info: dict[int, TypeInfo]) -> list:
    """Ships biggest first (then most numerous), capsules left out."""
    hulls = [
        {
            "type_id": type_id,
            "name": info[type_id].name,
            "count": count,
            "rank": info[type_id].rank,
        }
        for type_id, count in counts.items()
        if count and info[type_id].is_ship
    ]
    hulls.sort(key=lambda h: (h["rank"], -h["count"], h["name"]))
    return hulls


def ship_list(raw_counts: dict | None) -> list:
    """Feed ``{"type_id": count}`` -> sized hull list for a ping row."""
    counts: dict[int, int] = {}
    for key, count in (raw_counts or {}).items():
        try:
            counts[int(key)] = counts.get(int(key), 0) + int(count)
        except (TypeError, ValueError):
            continue
    if not counts:
        return []
    return hull_list(counts, type_info(counts))


def summarize_dscan(entries: list[DscanLine]) -> dict:
    counts = Counter(entry.type_id for entry in entries)
    names = {entry.type_id: entry.type_name for entry in entries}
    info = type_info(counts, names)

    hulls = hull_list(counts, info)
    classes: dict[str, dict] = {}
    for hull in hulls:
        name = info[hull["type_id"]].ship_class
        bucket = classes.setdefault(
            name,
            {
                "name": name,
                "count": 0,
                "rank": _CLASS_RANK.get(name, len(_CLASSES)),
                "hulls": [],
            },
        )
        bucket["count"] += hull["count"]
        bucket["hulls"].append(hull)

    capsules = sum(
        count for type_id, count in counts.items() if info[type_id].is_capsule
    )
    other = sorted(
        (
            {
                "type_id": type_id,
                "name": info[type_id].name,
                "group": info[type_id].other_label,
                "count": count,
            }
            for type_id, count in counts.items()
            if not info[type_id].is_ship and not info[type_id].is_capsule
        ),
        key=lambda row: (-row["count"], row["name"]),
    )
    ships = sum(hull["count"] for hull in hulls)
    return {
        "objects": len(entries),
        "ships": ships,
        "capsules": capsules,
        "other": sum(row["count"] for row in other),
        "classes": sorted(classes.values(), key=lambda c: c["rank"]),
        "hulls": hulls,
        "other_items": other[:50],
    }
