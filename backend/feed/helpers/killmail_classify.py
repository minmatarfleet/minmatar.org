from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from feed.constants import FACTION_AMARR, FACTION_MINMATAR, MILITIA_FACTION_IDS
from feed.helpers.affiliations import lookup_character_militia_factions


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


def _attacker_corporation_ids(
    killmails: list[dict[str, Any]],
) -> dict[int, int]:
    """Map each attacker to their most common corporation in the kill batch."""
    char_corps: dict[int, Counter[int]] = defaultdict(Counter)
    for km in killmails:
        for attacker in _attacker_rows(km):
            char_id = attacker.get("character_id")
            corp_id = attacker.get("corporation_id")
            if not char_id or not corp_id or corp_id == 1000125:
                continue
            char_corps[char_id][corp_id] += 1
    return {
        char_id: counts.most_common(1)[0][0]
        for char_id, counts in char_corps.items()
    }


def _esi_militia_factions(killmails: list[dict[str, Any]]) -> dict[int, int]:
    char_faction_counts: dict[int, Counter[int]] = defaultdict(Counter)
    for km in killmails:
        for attacker in _attacker_rows(km):
            char_id = attacker.get("character_id")
            if not char_id or attacker.get("corporation_id") == 1000125:
                continue
            faction_id = attacker.get("faction_id")
            if faction_id in MILITIA_FACTION_IDS:
                char_faction_counts[char_id][faction_id] += 1

    resolved: dict[int, int] = {}
    for char_id, counts in char_faction_counts.items():
        faction_id, _ = counts.most_common(1)[0]
        resolved[char_id] = faction_id
    return resolved


def resolve_attacker_militia_factions(
    killmails: list[dict[str, Any]],
) -> dict[int, int]:
    """Resolve enlisted pilots from killmail tags and feed character affiliations."""
    all_attackers = _unique_attacker_character_ids(killmails)
    if not all_attackers:
        return {}

    resolved = _esi_militia_factions(killmails)
    remaining = all_attackers - resolved.keys()
    if remaining:
        resolved.update(lookup_character_militia_factions(remaining))
    return resolved


def _dominant_faction_for_pilots(
    pilot_ids: set[int],
    char_factions: dict[int, int],
    *,
    threshold: float,
) -> int | None:
    if not pilot_ids:
        return None

    faction_pilots: Counter[int] = Counter()
    for char_id in pilot_ids:
        faction_id = char_factions.get(char_id)
        if faction_id in MILITIA_FACTION_IDS:
            faction_pilots[faction_id] += 1

    if not faction_pilots:
        return None

    faction_id, pilot_count = faction_pilots.most_common(1)[0]
    if pilot_count / len(pilot_ids) >= threshold:
        return faction_id
    return None


def _dominant_militia_bloc_faction(
    killmails: list[dict[str, Any]],
    char_factions: dict[int, int],
    *,
    threshold: float,
    min_bloc_pilots: int = 6,
) -> int | None:
    """Find an enlisted corporation bloc even when the wider fight is mixed."""
    char_corps = _attacker_corporation_ids(killmails)
    blocs: dict[int, set[int]] = defaultdict(set)
    for char_id, corp_id in char_corps.items():
        blocs[corp_id].add(char_id)

    best_faction: int | None = None
    best_pilot_count = 0
    for pilots in blocs.values():
        if len(pilots) < min_bloc_pilots:
            continue
        faction_id = _dominant_faction_for_pilots(
            pilots, char_factions, threshold=threshold
        )
        if faction_id is None:
            continue
        if len(pilots) > best_pilot_count:
            best_faction = faction_id
            best_pilot_count = len(pilots)
    return best_faction


def dominant_attacker_faction(
    killmails: list[dict[str, Any]],
    *,
    threshold: float = 0.75,
    min_bloc_pilots: int = 6,
) -> int | None:
    """Return militia faction when the fight or a corporation bloc is enlisted."""
    all_attackers = _unique_attacker_character_ids(killmails)
    if not all_attackers:
        return None

    char_factions = resolve_attacker_militia_factions(killmails)
    overall = _dominant_faction_for_pilots(
        all_attackers, char_factions, threshold=threshold
    )
    if overall is not None:
        return overall

    return _dominant_militia_bloc_faction(
        killmails,
        char_factions,
        threshold=threshold,
        min_bloc_pilots=min_bloc_pilots,
    )


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
