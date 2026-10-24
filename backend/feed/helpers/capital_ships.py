from __future__ import annotations

from typing import Any, Iterable

from eveuniverse.models import EveType

from eveonline.client import live_esi_allowed
from feed.constants import CAPITAL_SHIP_GROUPS


def is_capital_ship_type(ship_type_id: int | None) -> bool:
    if not ship_type_id:
        return False

    ship_type = EveType.objects.filter(id=ship_type_id).first()
    if ship_type is None:
        if not live_esi_allowed():
            return False
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
