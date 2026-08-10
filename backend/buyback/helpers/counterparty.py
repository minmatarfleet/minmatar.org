"""Resolve buyback ledger counterparties (character or corporation)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from eveonline.client import ESI_BASE_URL
from eveonline.models import EveCharacter, EveCorporation

logger = logging.getLogger(__name__)

KIND_CHARACTER = "character"
KIND_CORPORATION = "corporation"


@dataclass(frozen=True)
class Counterparty:
    id: int | None
    name: str
    kind: str


def _from_local(entity_id: int) -> Counterparty | None:
    char = EveCharacter.objects.filter(character_id=entity_id).first()
    if char is not None:
        return Counterparty(
            id=char.character_id,
            name=char.character_name or str(entity_id),
            kind=KIND_CHARACTER,
        )
    corp = EveCorporation.objects.filter(corporation_id=entity_id).first()
    if corp is not None:
        name = corp.name or corp.ticker or str(entity_id)
        return Counterparty(
            id=corp.corporation_id, name=name, kind=KIND_CORPORATION
        )
    return None


def _from_esi_names(entity_ids: list[int]) -> dict[int, Counterparty]:
    if not entity_ids:
        return {}
    try:
        resp = requests.post(
            f"{ESI_BASE_URL}/universe/names/",
            json=entity_ids,
            timeout=30,
        )
    except Exception as exc:
        logger.warning("universe/names failed: %s", exc)
        return {}
    if resp.status_code >= 400:
        logger.warning("universe/names HTTP %s", resp.status_code)
        return {}
    result: dict[int, Counterparty] = {}
    for row in resp.json() or []:
        try:
            eid = int(row["id"])
            category = str(row.get("category") or "")
            name = str(row.get("name") or eid)
        except (KeyError, TypeError, ValueError):
            continue
        if category == "character":
            kind = KIND_CHARACTER
        elif category == "corporation":
            kind = KIND_CORPORATION
        else:
            kind = category or ""
        result[eid] = Counterparty(id=eid, name=name, kind=kind)
    return result


def resolve_counterparties(
    entity_ids: set[int] | list[int],
) -> dict[int, Counterparty]:
    """Map entity id → Counterparty using local DB then ESI names."""
    ids = {int(i) for i in entity_ids if i}
    resolved: dict[int, Counterparty] = {}
    missing: list[int] = []
    for eid in ids:
        local = _from_local(eid)
        if local is not None:
            resolved[eid] = local
        else:
            missing.append(eid)
    if missing:
        resolved.update(_from_esi_names(missing))
    for eid in missing:
        if eid not in resolved:
            resolved[eid] = Counterparty(id=eid, name=str(eid), kind="")
    return resolved
