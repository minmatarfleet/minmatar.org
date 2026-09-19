"""Fill in the character names a killmail does not carry.

ESI killmails are all identifiers, so a killfeed built straight from them
reads "Unknown pilot" for every victim. Names we already hold come from our
own character table for free; the rest are resolved in bulk from the public
universe-names endpoint, which takes up to 1,000 ids in one call.
"""

from __future__ import annotations

import logging

from campaigns.models import CampaignKillmail, CampaignKillmailParticipant
from campaigns.services import esi_gate
from eveonline.client import EsiClient
from eveonline.models import EveCharacter

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def backfill_victim_names(limit: int = 1000) -> dict:
    """Name the victims of campaign killmails that have none yet."""
    rows = list(
        CampaignKillmail.objects.filter(
            victim_character_name="", victim_character_id__isnull=False
        ).values_list("id", "victim_character_id")[:limit]
    )
    if not rows:
        return {"pending": 0, "named": 0, "from_esi": 0}

    wanted = {character_id for _, character_id in rows}
    known = _names_we_already_have(wanted)
    from_esi = _resolve_missing(wanted - set(known))
    known.update(from_esi)

    named = 0
    for row_id, character_id in rows:
        name = known.get(character_id)
        if not name:
            continue
        CampaignKillmail.objects.filter(id=row_id).update(
            victim_character_name=name
        )
        named += 1

    _name_participants(known)

    return {"pending": len(rows), "named": named, "from_esi": len(from_esi)}


def _names_we_already_have(character_ids: set[int]) -> dict[int, str]:
    return dict(
        EveCharacter.objects.filter(character_id__in=character_ids)
        .exclude(character_name="")
        .values_list("character_id", "character_name")
    )


def _resolve_missing(character_ids: set[int]) -> dict[int, str]:
    """Ask ESI for the names we do not hold, in batches."""
    if not character_ids:
        return {}

    resolved: dict[int, str] = {}
    ids = sorted(character_ids)

    for start in range(0, len(ids), BATCH_SIZE):
        batch = ids[start : start + BATCH_SIZE]
        if not esi_gate.can_spend("universe-names"):
            logger.info("Stopping name resolution, ESI budget low")
            break

        response = EsiClient(None).resolve_universe_names(batch)
        esi_gate.spend("universe-names")
        if not response.success():
            esi_gate.record_error()
            logger.info("Name resolution failed: %s", response.error_text())
            break

        for entry in response.results() or []:
            if entry.get("category") != "character":
                continue
            resolved[entry["id"]] = entry.get("name", "")

    return resolved


def _name_participants(known: dict[int, str]) -> None:
    """Our own pilots show up on the mails too."""
    for character_id, name in known.items():
        CampaignKillmailParticipant.objects.filter(
            character_id=character_id, character_name=""
        ).update(character_name=name)
