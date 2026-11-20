import logging
import zlib
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from esi.exceptions import ESIErrorLimitException

from app.celery import app
from eveonline import character_sync
from eveonline.helpers.characters import (
    update_character_public_data as refresh_character_public_data,
)
from eveonline.helpers.alliances import tracked_alliance_ids
from eveonline.helpers.characters.corporation_history import (
    CORPORATION_HISTORY_TTL,
    sync_character_corporation_history,
)
from eveonline.models import EveCharacter, EveCharacterSyncState
from eveonline.utils import get_esi_downtime_countdown

logger = logging.getLogger(__name__)

# Pace initial/stale corporation-history backfill (~10 chars/min).
CORPORATION_HISTORY_BACKFILL_BATCH = 50

# The fan-out spreads members over its 4-hour window in 5-minute slots.
FANOUT_WINDOW = timedelta(hours=4)
FANOUT_SLOT = timedelta(minutes=5)
# Characters updated this recently (e.g. just added) are skipped by the
# fan-out.
FANOUT_RECENT = timedelta(hours=3, minutes=30)


@app.task(expires=FANOUT_WINDOW.total_seconds())
def update_character(eve_character_id):
    """Update a character's public data and every ESI section.

    Used by the fanout mode, new characters, and the tech router. Pacing
    comes from the caller (the fan-out spreads its countdowns); there is no
    Celery rate limit, and during ESI downtime it returns instead of
    re-queuing itself.
    """
    if get_esi_downtime_countdown() > 0:
        logger.info(
            "Skipping character update for %s during ESI downtime",
            eve_character_id,
        )
        return

    character = EveCharacter.objects.get(character_id=eve_character_id)
    if character.esi_deleted:
        logger.info(
            "Skipping update for ESI-deleted character %s (%s)",
            character.character_name,
            eve_character_id,
        )
        return

    logger.info(
        "Updating character %s (%s)",
        character.character_name,
        eve_character_id,
    )
    refresh_character_public_data(eve_character_id)
    character.refresh_from_db()
    if character.esi_suspended:
        logger.info(
            "Skipping update for ESI suspended character %s",
            eve_character_id,
        )
        return
    character_sync.run_character_sync(character, force=True)


@app.task()
def update_character_urgent(eve_character_id):
    """A new character's first fetch: every section, right away."""
    update_character(eve_character_id)


@app.task
def update_all_character_public_data() -> int:
    """Refresh public ESI fields (corp-change history sync lives in public_data)."""
    character_ids = list(
        EveCharacter.objects.filter(esi_deleted=False).values_list(
            "character_id", flat=True
        )
    )
    updated = 0
    for index, character_id in enumerate(character_ids):
        try:
            if refresh_character_public_data(character_id):
                updated += 1
        except ESIErrorLimitException:
            logger.warning(
                "ESI error limited during public data sweep after %d update(s); "
                "aborting remaining %d character(s)",
                updated,
                len(character_ids) - index,
            )
            return updated
    logger.info(
        "Updated public data for %d of %d character(s)",
        updated,
        len(character_ids),
    )
    return updated


@app.task(rate_limit="10/m")
def sync_character_corporation_history_task(eve_character_id: int) -> bool:
    """Paced single-character corporation history sync (backfill / stale TTL)."""
    character = EveCharacter.objects.filter(
        character_id=eve_character_id, esi_deleted=False
    ).first()
    if not character:
        return False
    try:
        return sync_character_corporation_history(character)
    except ESIErrorLimitException:
        logger.warning(
            "ESI error limited syncing corporation history for %s",
            eve_character_id,
        )
        raise


@app.task
def queue_stale_character_corporation_history(
    batch_size: int = CORPORATION_HISTORY_BACKFILL_BATCH,
) -> int:
    """Queue paced history syncs for characters with null/stale synced_at."""
    cutoff = timezone.now() - CORPORATION_HISTORY_TTL
    character_ids = list(
        EveCharacter.objects.filter(esi_deleted=False)
        .filter(
            Q(corporation_history_synced_at__isnull=True)
            | Q(corporation_history_synced_at__lt=cutoff)
        )
        .order_by("corporation_history_synced_at", "character_id")
        .values_list("character_id", flat=True)[:batch_size]
    )
    for character_id in character_ids:
        sync_character_corporation_history_task.apply_async(
            args=[character_id],
        )
    logger.info(
        "Queued corporation history sync for %d character(s)",
        len(character_ids),
    )
    return len(character_ids)


@app.task
def update_alliance_characters():
    """Fanout mode: queue update_character for every member character,
    spread across the 4-hour window.

    Returns early in scheduled mode, where queue_due_character_syncs keeps
    each section fresh on its own interval.
    """
    if character_sync.sync_mode() == character_sync.MODE_SCHEDULED:
        return 0
    # Tracked scope: characters in any alliance we sync, not only FL33T/BUILD.
    alliance_characters = EveCharacter.objects.filter(
        alliance_id__in=tracked_alliance_ids()
    )
    users_with_alliance_chars = User.objects.filter(
        evecharacter__in=alliance_characters
    ).distinct()
    recent = EveCharacterSyncState.objects.filter(
        section=character_sync.ASSETS,
        attempted_at__gte=timezone.now() - FANOUT_RECENT,
    ).values("character_id")
    all_characters = (
        EveCharacter.objects.filter(
            user__in=users_with_alliance_chars,
            esi_deleted=False,
        )
        .exclude(token=None)
        .exclude(pk__in=recent)
    )

    character_ids = list(all_characters.values_list("character_id", flat=True))
    logger.info(
        "Queuing update_character for %d alliance character(s)",
        len(character_ids),
    )
    for character_id in character_ids:
        countdown = fanout_countdown(character_id)
        update_character.apply_async(
            args=[character_id],
            countdown=countdown,
            expires=countdown + 60 * 60,
        )
    return len(character_ids)


def fanout_countdown(character_id: int) -> int:
    """A stable 5-minute slot in the 4-hour window for this character."""
    slots = int(FANOUT_WINDOW / FANOUT_SLOT)
    slot = zlib.crc32(str(character_id).encode()) % slots
    return int(slot * FANOUT_SLOT.total_seconds())
