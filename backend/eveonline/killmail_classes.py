"""How a killmail is classified, in one place.

Every rollup that splits kills into pods and ships, or into solo, small-gang
and fleet fights, imports these instead of keeping its own copy. This module
imports nothing, so any app can use it.

Counting rule: a person counts a killmail once however many of their
characters were on it, and a group (corporation, tribe, alliance) counts a
killmail once however many of its members were on it.
"""

from __future__ import annotations

CAPSULE_TYPE_ID = 670
GENOLUTION_CAPSULE_TYPE_ID = 33328
CAPSULE_TYPE_IDS = frozenset({CAPSULE_TYPE_ID, GENOLUTION_CAPSULE_TYPE_ID})

# Attackers on the mail, every pilot (NPCs included), not just ours.
SOLO_MAX_ATTACKERS = 1
SMALL_GANG_MAX_ATTACKERS = 10


def is_capsule(type_id: int | None) -> bool:
    """True for either capsule hull (the plain and the Genolution pod)."""
    return type_id is not None and int(type_id) in CAPSULE_TYPE_IDS
