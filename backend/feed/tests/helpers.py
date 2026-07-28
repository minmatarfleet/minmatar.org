from __future__ import annotations

from datetime import datetime, timezone


def make_killmail_payload(
    killmail_id: int,
    *,
    solar_system_id: int = 30002538,
    killmail_time: datetime | None = None,
    faction_id: int | None = 500002,
    victim_faction_id: int | None = None,
    attacker_count: int = 8,
    attacker_id_base: int = 90000000,
    ship_type_id: int = 22468,
    attacker_ship_type_id: int = 22468,
) -> dict:
    """Build R2Z2-style payload for tests."""
    if killmail_time is None:
        killmail_time = datetime(2026, 6, 19, 17, 25, 8, tzinfo=timezone.utc)

    attackers = []
    for i in range(attacker_count):
        attacker: dict = {
            "character_id": attacker_id_base + i,
            "corporation_id": 98000000 + (0 if faction_id == 500002 else 1),
            "alliance_id": 99000000 + (0 if faction_id == 500002 else 1),
            "ship_type_id": attacker_ship_type_id,
            "damage_done": 1000,
            "final_blow": i == 0,
        }
        if faction_id is not None:
            attacker["faction_id"] = faction_id
        attackers.append(attacker)

    victim: dict = {
        "character_id": 80000000 + killmail_id % 1000,
        "corporation_id": 98000001,
        "ship_type_id": ship_type_id,
        "damage_taken": 5000,
    }
    if victim_faction_id is not None:
        victim["faction_id"] = victim_faction_id

    raw = {
        "killmail_id": killmail_id,
        "killmail_time": killmail_time.isoformat().replace("+00:00", "Z"),
        "solar_system_id": solar_system_id,
        "victim": victim,
        "attackers": attackers,
    }
    return {
        "killmail": raw,
        "hash": f"hash{killmail_id:012d}",
        "zkb": {"npc": False, "totalValue": 1000000},
        "sequence_id": killmail_id,
    }


def jita_killmail_payload(killmail_id: int = 99999999) -> dict:
    return make_killmail_payload(killmail_id, solar_system_id=30000142)
