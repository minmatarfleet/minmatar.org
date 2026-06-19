"""Celery tasks for industry: syncing jobs from ESI for order assignees."""

import logging

from app.celery import app
from eveonline.helpers.characters.update import update_character_industry_jobs
from eveonline.models import EveCharacter

from industry.models import IndustryOrderItemAssignment

logger = logging.getLogger(__name__)


@app.task()
def sync_industry_jobs_for_character(character_id: int) -> None:
    """Fetch and store industry jobs for a single character from ESI (EveCharacterIndustryJob)."""
    try:
        update_character_industry_jobs(character_id)
    except Exception as e:
        logger.exception(
            "Failed to sync industry jobs for character %s: %s",
            character_id,
            e,
        )


@app.task()
def sync_industry_jobs_for_order_assignees() -> None:
    """
    For every character assigned to part of an industry order, sync industry
    jobs for that character and all their related characters (same user).
    Runs every 4 hours via Celery beat.
    """
    # Distinct character PKs that have at least one assignment
    assigned_character_pks = set(
        IndustryOrderItemAssignment.objects.values_list(
            "character_id", flat=True
        ).distinct()
    )

    assigned_rows = EveCharacter.objects.filter(
        pk__in=assigned_character_pks
    ).values_list("user_id", "character_id")

    character_ids = set()
    user_ids = {user_id for user_id, _ in assigned_rows if user_id}
    for _, character_id in assigned_rows:
        character_ids.add(character_id)

    if user_ids:
        character_ids.update(
            EveCharacter.objects.filter(user_id__in=user_ids).values_list(
                "character_id", flat=True
            )
        )

    for character_id in character_ids:
        sync_industry_jobs_for_character.delay(character_id)

    logger.info(
        "Scheduled industry job sync for %s character(s) (order assignees and related)",
        len(character_ids),
    )
