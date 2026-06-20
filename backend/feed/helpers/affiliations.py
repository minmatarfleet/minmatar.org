from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

from eveonline.client import EsiClient
from feed.constants import MILITIA_FACTION_IDS
from feed.models import FeedCharacterAffiliation
from feed.rollups.config import get_rollup_config

logger = logging.getLogger(__name__)


def _affiliation_sync_config() -> dict[str, Any]:
    return get_rollup_config("affiliation_sync")


def _militia_faction_id(faction_id: int | None) -> int | None:
    if faction_id in MILITIA_FACTION_IDS:
        return faction_id
    return None


def _upsert_character_from_killmail(
    *,
    character_id: int,
    corporation_id: int | None,
    alliance_id: int | None,
    faction_id: int | None,
) -> None:
    """Apply killmail participant data without overwriting ESI-checked rows."""
    stored_faction_id = _militia_faction_id(faction_id)
    has_snapshot = (
        stored_faction_id is not None
        or corporation_id is not None
        or alliance_id is not None
    )
    if not has_snapshot:
        FeedCharacterAffiliation.objects.get_or_create(
            character_id=character_id,
        )
        return

    row, created = FeedCharacterAffiliation.objects.get_or_create(
        character_id=character_id,
        defaults={
            "faction_id": stored_faction_id,
            "corporation_id": corporation_id,
            "alliance_id": alliance_id,
        },
    )
    if created:
        return

    if row.esi_checked_at is not None:
        updates: dict[str, Any] = {}
        if corporation_id is not None and row.corporation_id is None:
            updates["corporation_id"] = corporation_id
        if alliance_id is not None and row.alliance_id is None:
            updates["alliance_id"] = alliance_id
        if updates:
            FeedCharacterAffiliation.objects.filter(pk=row.pk).update(
                **updates
            )
        return

    updates: dict[str, Any] = {}
    if corporation_id is not None:
        updates["corporation_id"] = corporation_id
    if alliance_id is not None:
        updates["alliance_id"] = alliance_id
    if stored_faction_id is not None:
        updates["faction_id"] = stored_faction_id
    if updates:
        FeedCharacterAffiliation.objects.filter(pk=row.pk).update(**updates)


def apply_killmail_affiliations(
    raw: dict[str, Any],
    *,
    confirmed_at=None,
) -> None:
    """Eagerly populate characters from killmail participant data."""
    del confirmed_at  # killmail snapshots do not mark ESI source-of-truth checks

    for attacker in raw.get("attackers") or []:
        char_id = attacker.get("character_id")
        if not char_id:
            continue
        _upsert_character_from_killmail(
            character_id=char_id,
            corporation_id=attacker.get("corporation_id"),
            alliance_id=attacker.get("alliance_id"),
            faction_id=attacker.get("faction_id"),
        )

    victim = raw.get("victim") or {}
    victim_char = victim.get("character_id")
    if victim_char:
        _upsert_character_from_killmail(
            character_id=victim_char,
            corporation_id=victim.get("corporation_id"),
            alliance_id=victim.get("alliance_id"),
            faction_id=victim.get("faction_id"),
        )


def lookup_character_militia_factions(
    character_ids: set[int],
) -> dict[int, int]:
    if not character_ids:
        return {}

    return {
        row.character_id: row.faction_id
        for row in FeedCharacterAffiliation.objects.filter(
            character_id__in=character_ids,
            faction_id__in=MILITIA_FACTION_IDS,
        )
    }


def _fetch_character_affiliations_batch(
    character_ids: list[int],
) -> tuple[dict[int, dict[str, Any]], set[int]]:
    """Return affiliations from ESI and IDs whose chunk request failed."""
    if not character_ids:
        return {}, set()

    cfg = _affiliation_sync_config()
    chunk_size = cfg.get("esi_affiliation_chunk_size", 1000)
    by_id: dict[int, dict[str, Any]] = {}
    failed: set[int] = set()

    for offset in range(0, len(character_ids), chunk_size):
        chunk = character_ids[offset : offset + chunk_size]
        response = EsiClient(None).get_character_affiliations(chunk)
        if not response.success():
            logger.warning(
                "ESI affiliations batch failed for %d characters: %s",
                len(chunk),
                response.error_text(),
            )
            failed.update(chunk)
            continue

        for row in response.results() or []:
            by_id[row["character_id"]] = row

    return by_id, failed


def _apply_esi_affiliation_result(
    character_id: int,
    result: dict[str, Any] | None,
) -> bool:
    now = timezone.now()
    stored_faction_id = None
    corporation_id = None
    alliance_id = None
    if result is not None:
        stored_faction_id = _militia_faction_id(result.get("faction_id"))
        corporation_id = result.get("corporation_id")
        alliance_id = result.get("alliance_id")

    FeedCharacterAffiliation.objects.filter(
        character_id=character_id,
    ).update(
        faction_id=stored_faction_id,
        corporation_id=corporation_id,
        alliance_id=alliance_id,
        esi_checked_at=now,
    )
    return True


def populate_character_affiliations_from_esi(character_ids: list[int]) -> int:
    """Resolve character rows via ESI POST /characters/affiliation/."""
    if not character_ids:
        return 0

    affiliations, failed = _fetch_character_affiliations_batch(character_ids)
    updated = 0
    for character_id in character_ids:
        if character_id in failed:
            continue
        if _apply_esi_affiliation_result(
            character_id,
            affiliations.get(character_id),
        ):
            updated += 1
    return updated


def populate_character_affiliation(character_id: int) -> bool:
    return populate_character_affiliations_from_esi([character_id]) > 0


def refresh_character_affiliation(character_id: int) -> bool:
    return populate_character_affiliations_from_esi([character_id]) > 0


def populate_unchecked_character_affiliations_batch() -> int:
    """ESI batch for characters never checked against ESI affiliations."""
    cfg = _affiliation_sync_config()
    batch_size = cfg.get("populate_batch_size", 200)
    character_ids = list(
        FeedCharacterAffiliation.objects.filter(esi_checked_at__isnull=True)
        .order_by("created_at")
        .values_list("character_id", flat=True)[:batch_size]
    )
    return populate_character_affiliations_from_esi(character_ids)


def refresh_stale_character_affiliations_batch() -> int:
    """ESI batch for characters whose ESI check is stale."""
    cfg = _affiliation_sync_config()
    batch_size = cfg.get("refresh_batch_size", 150)
    stale_hours = cfg.get("refresh_stale_hours", 168)
    stale_cutoff = timezone.now() - timedelta(hours=stale_hours)

    character_ids = list(
        FeedCharacterAffiliation.objects.filter(
            esi_checked_at__lt=stale_cutoff,
        )
        .order_by("esi_checked_at")
        .values_list("character_id", flat=True)[:batch_size]
    )
    return populate_character_affiliations_from_esi(character_ids)


# Backwards-compatible aliases.
discover_character = _upsert_character_from_killmail
discover_character_affiliation = _upsert_character_from_killmail
discover_characters_from_killmail = apply_killmail_affiliations
discover_entities_from_killmail = apply_killmail_affiliations
populate_pending_character_affiliations_batch = (
    populate_unchecked_character_affiliations_batch
)
populate_empty_character_affiliations_batch = (
    populate_unchecked_character_affiliations_batch
)
