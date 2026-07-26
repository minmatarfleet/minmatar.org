from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from eveuniverse.models import EveType

from feed.constants import CAPITAL_SHIP_GROUPS


def is_capital_ship_type(ship_type_id: int | None) -> bool:
    if not ship_type_id:
        return False

    ship_type = EveType.objects.filter(id=ship_type_id).first()
    if ship_type is None:
        ship_type, _ = EveType.objects.get_or_create_esi(id=ship_type_id)
    group = ship_type.eve_group
    if group is None:
        return False
    return group.name in CAPITAL_SHIP_GROUPS


def collect_killmail_ship_type_ids(raw: dict[str, Any]) -> set[int]:
    ship_type_ids: set[int] = set()
    victim = raw.get("victim") or {}
    victim_ship_type_id = victim.get("ship_type_id")
    if victim_ship_type_id:
        ship_type_ids.add(int(victim_ship_type_id))

    for attacker in raw.get("attackers") or []:
        ship_type_id = attacker.get("ship_type_id")
        if ship_type_id:
            ship_type_ids.add(int(ship_type_id))
    return ship_type_ids


def filter_capital_ship_type_ids(type_ids: Iterable[int]) -> set[int]:
    ids = {int(type_id) for type_id in type_ids if type_id}
    if not ids:
        return set()

    capital_ids = set(
        EveType.objects.filter(
            id__in=ids,
            eve_group__name__in=CAPITAL_SHIP_GROUPS,
        ).values_list("id", flat=True)
    )
    for type_id in ids - capital_ids:
        if is_capital_ship_type(type_id):
            capital_ids.add(type_id)
    return capital_ids


def killmail_involves_capital(raw: dict[str, Any]) -> bool:
    return bool(
        filter_capital_ship_type_ids(collect_killmail_ship_type_ids(raw))
    )


def capital_ships_on_killmail(
    raw: dict[str, Any],
) -> list[tuple[int, int, str]]:
    """Return (type_id, count, role) for capital hulls on the mail.

    Role is ``victim`` or ``attacker``.
    """
    victim = raw.get("victim") or {}
    victim_ship_type_id = victim.get("ship_type_id")
    capital_type_ids = filter_capital_ship_type_ids(
        collect_killmail_ship_type_ids(raw)
    )
    if not capital_type_ids:
        return []

    attacker_counts: Counter[int] = Counter()
    for attacker in raw.get("attackers") or []:
        if attacker.get("corporation_id") == 1000125:
            continue
        ship_type_id = attacker.get("ship_type_id")
        if ship_type_id and int(ship_type_id) in capital_type_ids:
            attacker_counts[int(ship_type_id)] += 1

    rows: list[tuple[int, int, str]] = []
    if victim_ship_type_id and int(victim_ship_type_id) in capital_type_ids:
        rows.append((int(victim_ship_type_id), 1, "victim"))
    for type_id, count in attacker_counts.most_common():
        rows.append((type_id, count, "attacker"))
    return rows
