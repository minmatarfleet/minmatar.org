"""Work out which system a d-scan was taken in, from the paste alone.

Celestials carry their system's name: ``Amamake VII``, ``Amamake VII -
Moon 3``, ``Amamake - Star``, ``Customs Office (Amamake VII)``. When none
is in range, the stargates still are, and their names are the
neighbouring systems: ``Stargate (Bosboger)``. The one system linked to
every one of those neighbours is where the pilot sits.
"""

from __future__ import annotations

import re
from collections import Counter

from intel.services.fixtures import load_map, system_ids_by_name
from intel.services.paste import DscanLine

_ROMAN = re.compile(r"^(.+?) ([IVXLC]+)$")
_PAREN = re.compile(r"\(([^()]+)\)\s*$")


def _celestial_system(name: str) -> str | None:
    """The system part of a celestial's name, or None for anything else."""
    head, _, rest = name.partition(" - ")
    match = _ROMAN.match(head.strip())
    if match:
        return match.group(1)
    if rest.strip() == "Star":
        return head.strip()
    paren = _PAREN.search(name)
    if paren:
        match = _ROMAN.match(paren.group(1).strip())
        if match:
            return match.group(1)
    return None


def _gate_neighbour(entry: DscanLine) -> str | None:
    if not entry.type_name.startswith("Stargate"):
        return None
    paren = _PAREN.search(entry.name)
    return paren.group(1).strip() if paren else None


def system_from_scan(entries: list[DscanLine]) -> tuple[int, str] | None:
    """``(system id, name)`` for the d-scan's system, or None if unsure."""
    by_name = system_ids_by_name()
    systems = load_map().get("systems", {})
    if not by_name:
        return None

    votes: Counter = Counter()
    for entry in entries:
        system = _celestial_system(entry.name)
        system_id = by_name.get(system.lower()) if system else None
        if system_id:
            votes[system_id] += 1
    if votes:
        # A pilot can name a ship after a planet; the real system has
        # far more celestials on scan than any such ship.
        system_id = votes.most_common(1)[0][0]
        return system_id, systems.get(str(system_id), "")

    neighbours = {
        by_name[name.lower()]
        for name in filter(None, map(_gate_neighbour, entries))
        if name.lower() in by_name
    }
    if not neighbours:
        return None
    edges = load_map().get("edges", {})
    matches = [
        int(system_id)
        for system_id, linked in edges.items()
        if neighbours <= set(linked)
    ]
    if len(matches) != 1:
        return None
    return matches[0], systems.get(str(matches[0]), "")
