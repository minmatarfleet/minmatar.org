from __future__ import annotations

from datetime import datetime, timezone


def make_killmail_payload(
    killmail_id: int,
    *,
    solar_system_id: int = 30002538,
    killmail_time: datetime | None = None,
    faction_id: int = 500002,
    attacker_count: int = 8,
    ship_type_id: int = 22468,
    attacker_ship_type_id: int = 22468,
) -> dict:
    """Build R2Z2-style payload for tests."""
    if killmail_time is None:
        killmail_time = datetime(2026, 6, 19, 17, 25, 8, tzinfo=timezone.utc)

    attackers = [
        {
            "character_id": 90000000 + i,
            "corporation_id": 98000000,
            "alliance_id": 99000000,
            "faction_id": faction_id,
            "ship_type_id": attacker_ship_type_id,
            "damage_done": 1000,
            "final_blow": i == 0,
        }
        for i in range(attacker_count)
    ]
    raw = {
        "killmail_id": killmail_id,
        "killmail_time": killmail_time.isoformat().replace("+00:00", "Z"),
        "solar_system_id": solar_system_id,
        "victim": {
            "character_id": 80000000 + killmail_id % 1000,
            "corporation_id": 98000001,
            "ship_type_id": ship_type_id,
            "damage_taken": 5000,
        },
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
