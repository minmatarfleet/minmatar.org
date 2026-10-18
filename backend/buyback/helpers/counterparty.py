"""Resolve buyback ledger counterparties (character or corporation)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from eveonline.client import EsiClient
from eveonline.models import EveCharacter, EveCorporation

logger = logging.getLogger(__name__)

KIND_CHARACTER = "character"
KIND_CORPORATION = "corporation"
# POST /universe/names/ takes at most 1000 ids.
UNIVERSE_NAMES_CHUNK = 1000


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


def _esi_name_rows(entity_ids: list[int]) -> list[dict]:
    client = EsiClient(None)
    rows: list[dict] = []
    for start in range(0, len(entity_ids), UNIVERSE_NAMES_CHUNK):
        chunk = entity_ids[start : start + UNIVERSE_NAMES_CHUNK]
        response = client.resolve_universe_names(chunk)
        if not response.success():
            logger.warning("universe/names failed: %s", response.error_text())
            continue
        rows.extend(response.results() or [])
    return rows


def _from_esi_names(entity_ids: list[int]) -> dict[int, Counterparty]:
    if not entity_ids:
        return {}
    result: dict[int, Counterparty] = {}
    for row in _esi_name_rows(entity_ids):
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
