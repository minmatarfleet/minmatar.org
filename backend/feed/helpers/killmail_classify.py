from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from feed.constants import FACTION_AMARR, FACTION_MINMATAR, MILITIA_FACTION_IDS


def is_npc_kill(zkb_meta: dict[str, Any]) -> bool:
    return bool(zkb_meta.get("npc"))


def _attacker_rows(killmail: dict[str, Any]) -> list[dict[str, Any]]:
    return killmail.get("attackers") or []


def _victim_row(killmail: dict[str, Any]) -> dict[str, Any]:
    return killmail.get("victim") or {}


def attacker_pilot_count(killmail: dict[str, Any]) -> int:
    ids = {
        a.get("character_id")
        for a in _attacker_rows(killmail)
        if a.get("character_id")
        and not a.get("corporation_id") == 1000125  # CONCORD
    }
    ids.discard(None)
    return len(ids)


def extract_militia_character_ids(
    killmail: dict[str, Any],
) -> list[tuple[int, int, str]]:
    """Return (character_id, faction_id, role) for militia chars on mail."""
    results: list[tuple[int, int, str]] = []
    victim = _victim_row(killmail)
    victim_char = victim.get("character_id")
    victim_faction = victim.get("faction_id")
    if victim_char and victim_faction in MILITIA_FACTION_IDS:
        results.append((victim_char, victim_faction, "victim"))

    for attacker in _attacker_rows(killmail):
        char_id = attacker.get("character_id")
        faction_id = attacker.get("faction_id")
        if char_id and faction_id in MILITIA_FACTION_IDS:
            results.append((char_id, faction_id, "attacker"))
    return results


def _unique_attacker_character_ids(
    killmails: list[dict[str, Any]],
) -> set[int]:
    ids: set[int] = set()
    for km in killmails:
        for attacker in _attacker_rows(km):
            char_id = attacker.get("character_id")
            if not char_id or attacker.get("corporation_id") == 1000125:
                continue
            ids.add(char_id)
    return ids


def dominant_attacker_faction(
    killmails: list[dict[str, Any]],
    *,
    threshold: float = 0.5,
) -> int | None:
    """Return militia faction only if a majority of unique attackers are enlisted."""
    all_attackers = _unique_attacker_character_ids(killmails)
    if not all_attackers:
        return None

    char_faction_counts: dict[int, Counter[int]] = defaultdict(Counter)
    for km in killmails:
        for attacker in _attacker_rows(km):
            char_id = attacker.get("character_id")
            if not char_id or attacker.get("corporation_id") == 1000125:
                continue
            faction_id = attacker.get("faction_id")
            if faction_id in MILITIA_FACTION_IDS:
                char_faction_counts[char_id][faction_id] += 1

    faction_pilots: Counter[int] = Counter()
    for char_id in all_attackers:
        counts = char_faction_counts.get(char_id)
        if not counts:
            continue
        faction_id, _ = counts.most_common(1)[0]
        faction_pilots[faction_id] += 1

    if not faction_pilots:
        return None

    faction_id, pilot_count = faction_pilots.most_common(1)[0]
    if pilot_count / len(all_attackers) > threshold:
        return faction_id
    return None


def top_ship_names(
    killmails: list[dict[str, Any]], limit: int = 3
) -> list[str]:
    """Return top victim ship type names from raw killmails (type_id only fallback)."""
    type_counts: Counter[int] = Counter()
    for km in killmails:
        victim = _victim_row(km)
        ship_type_id = victim.get("ship_type_id")
        if ship_type_id:
            type_counts[ship_type_id] += 1
    # Without type name lookup, use type IDs as strings
    return [str(tid) for tid, _ in type_counts.most_common(limit)]


def faction_to_accent_key(faction_id: int | None) -> str:
    if faction_id == FACTION_MINMATAR:
        return "minmatar"
    if faction_id == FACTION_AMARR:
        return "amarr"
    return "pirate"


def faction_to_label(faction_id: int) -> str:
    if faction_id == FACTION_MINMATAR:
        return "Minmatar militia"
    if faction_id == FACTION_AMARR:
        return "Amarr militia"
    return "Unknown"
