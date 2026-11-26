"""Sync ESI character corporation history with join-time alliance/faction enrichment."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from django.utils import timezone

from eveonline.client import esi_public, live_esi_allowed
from eveonline.helpers.esi import parse_esi_date, raise_if_esi_error_limited
from eveonline.models import (
    EveCharacter,
    EveCharacterCorporationHistory,
    EveCorporation,
    EveCorporationAllianceHistory,
    EveCorporationAllianceHistorySync,
)

logger = logging.getLogger(__name__)

CORPORATION_HISTORY_TTL = timedelta(hours=24)
ALLIANCE_HISTORY_TTL = timedelta(hours=1)


def character_corporation_history_is_stale(
    character: EveCharacter,
    *,
    force: bool = False,
    include_never_synced: bool = True,
) -> bool:
    """True when we should hit ESI for this character's corporation history."""
    if force:
        return True
    if character.corporation_history_synced_at is None:
        return include_never_synced
    if (
        timezone.now() - character.corporation_history_synced_at
        >= CORPORATION_HISTORY_TTL
    ):
        return True
    latest = (
        character.corporation_history.order_by("-start_date", "-record_id")
        .only("corporation_id")
        .first()
    )
    if (
        latest
        and character.corporation_id
        and latest.corporation_id != character.corporation_id
    ):
        return True
    return False


def alliance_id_at(
    rows: list[EveCorporationAllianceHistory], join_date: datetime
) -> Optional[int]:
    """Alliance the corp was in at join_date. rows should be newest-first."""
    for row in rows:
        if row.start_date <= join_date:
            return row.alliance_id
    return None


def _alliance_history_qs(corporation_id: int):
    return EveCorporationAllianceHistory.objects.filter(
        corporation_id=corporation_id
    ).order_by("-start_date", "-record_id")


def ensure_corporation_alliance_history(
    corporation_id: int, *, force: bool = False
) -> list[EveCorporationAllianceHistory]:
    """Return cached alliance-history rows, refreshing from ESI when stale."""
    sync = EveCorporationAllianceHistorySync.objects.filter(
        corporation_id=corporation_id
    ).first()
    if (
        sync
        and not force
        and timezone.now() - sync.synced_at < ALLIANCE_HISTORY_TTL
    ):
        return list(_alliance_history_qs(corporation_id))

    response = esi_public().get_corporation_alliance_history(corporation_id)
    if not response.success():
        raise_if_esi_error_limited(response)
        logger.warning(
            "ESI error %s fetching alliance history for corp %s",
            response.response_code,
            corporation_id,
        )
        return list(_alliance_history_qs(corporation_id))

    seen_record_ids: set[int] = set()
    for item in response.results() or []:
        record_id = item.get("record_id")
        start_date = parse_esi_date(item.get("start_date"))
        if record_id is None or start_date is None:
            continue
        seen_record_ids.add(record_id)
        EveCorporationAllianceHistory.objects.update_or_create(
            corporation_id=corporation_id,
            record_id=record_id,
            defaults={
                "alliance_id": item.get("alliance_id"),
                "start_date": start_date,
                "is_deleted": bool(item.get("is_deleted", False)),
            },
        )
    qs = EveCorporationAllianceHistory.objects.filter(
        corporation_id=corporation_id
    )
    if seen_record_ids:
        qs.exclude(record_id__in=seen_record_ids).delete()
    else:
        qs.delete()

    EveCorporationAllianceHistorySync.objects.update_or_create(
        corporation_id=corporation_id,
        defaults={"synced_at": timezone.now()},
    )
    return list(_alliance_history_qs(corporation_id))


def _faction_for_join(
    character: EveCharacter,
    *,
    corporation_id: int,
    resolved_alliance_id: Optional[int],
    is_current_membership: bool,
    existing_faction_id: Optional[int],
) -> Optional[int]:
    """Best-effort faction at join; never overwrites a stored non-null."""
    if existing_faction_id is not None:
        return existing_faction_id
    if is_current_membership and character.faction_id:
        return character.faction_id

    local_corp = (
        EveCorporation.objects.filter(corporation_id=corporation_id)
        .select_related("alliance", "faction")
        .first()
    )
    if not local_corp or not local_corp.faction_id:
        return None
    local_alliance_id = (
        local_corp.alliance.alliance_id if local_corp.alliance else None
    )
    if resolved_alliance_id == local_alliance_id:
        return local_corp.faction_id
    return None


def sync_character_corporation_history(
    character: EveCharacter,
    *,
    force: bool = False,
    include_never_synced: bool = True,
) -> bool:
    """
    Fetch and upsert corporation history when TTL / policy says so.

    Returns True when a sync ran. Raises ESIErrorLimitException for bulk abort.
    Other ESI failures log and return False (does not mark character deleted).
    """
    if character.esi_deleted:
        return False
    if not live_esi_allowed():
        logger.info(
            "Skipping corporation history ESI for %s during tests",
            character.character_id,
        )
        return False
    if not character_corporation_history_is_stale(
        character,
        force=force,
        include_never_synced=include_never_synced,
    ):
        return False

    response = esi_public().get_character_corporation_history(
        character.character_id
    )
    if not response.success():
        raise_if_esi_error_limited(response)
        logger.warning(
            "ESI error %s fetching corporation history for character %s",
            response.response_code,
            character.character_id,
        )
        return False

    parsed: list[dict] = []
    for item in response.results() or []:
        record_id = item.get("record_id")
        corporation_id = item.get("corporation_id")
        start_date = parse_esi_date(item.get("start_date"))
        if record_id is None or corporation_id is None or start_date is None:
            continue
        parsed.append(
            {
                "record_id": record_id,
                "corporation_id": corporation_id,
                "start_date": start_date,
                "is_deleted": bool(item.get("is_deleted", False)),
            }
        )
    parsed.sort(key=lambda r: (r["start_date"], r["record_id"]), reverse=True)

    alliance_cache: dict[int, list[EveCorporationAllianceHistory]] = {}
    seen_record_ids: set[int] = set()
    existing_by_record = {
        row.record_id: row
        for row in EveCharacterCorporationHistory.objects.filter(
            character=character
        )
    }

    for index, row in enumerate(parsed):
        record_id = row["record_id"]
        corporation_id = row["corporation_id"]
        start_date = row["start_date"]
        seen_record_ids.add(record_id)

        if corporation_id not in alliance_cache:
            alliance_cache[corporation_id] = (
                ensure_corporation_alliance_history(corporation_id)
            )
        resolved_alliance_id = alliance_id_at(
            alliance_cache[corporation_id], start_date
        )
        existing = existing_by_record.get(record_id)
        EveCharacterCorporationHistory.objects.update_or_create(
            character=character,
            record_id=record_id,
            defaults={
                "corporation_id": corporation_id,
                "start_date": start_date,
                "is_deleted": row["is_deleted"],
                "alliance_id": resolved_alliance_id,
                "faction_id": _faction_for_join(
                    character,
                    corporation_id=corporation_id,
                    resolved_alliance_id=resolved_alliance_id,
                    is_current_membership=index == 0,
                    existing_faction_id=(
                        existing.faction_id if existing else None
                    ),
                ),
            },
        )

    EveCharacterCorporationHistory.objects.filter(character=character).exclude(
        record_id__in=seen_record_ids
    ).delete()

    character.corporation_history_synced_at = timezone.now()
    character.save(update_fields=["corporation_history_synced_at"])
    logger.info(
        "Synced corporation history for %s (%d row(s))",
        character.summary(),
        len(seen_record_ids),
    )
    return True
