"""Helpers for syncing character industry jobs from ESI."""

import logging
from datetime import datetime
from decimal import Decimal

import pytz
from django.utils import timezone
from esi.models import Token

from eveonline.client import EsiClient
from eveonline.models import EveCharacter

from industry.models import IndustryJob

logger = logging.getLogger(__name__)

INDUSTRY_JOBS_SCOPE = "esi-industry.read_character_jobs.v1"


def _parse_esi_date(value):
    """Parse ESI ISO date string to timezone-aware datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        return (
            timezone.make_aware(value) if timezone.is_naive(value) else value
        )
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timezone.is_naive(dt):
        dt = pytz.UTC.localize(dt)
    return dt


def sync_character_industry_jobs(character_id: int) -> None:
    """
    Fetch industry jobs for a character from ESI and upsert into IndustryJob.
    Skips if character not found, ESI suspended, or no valid token.
    """
    character = EveCharacter.objects.filter(character_id=character_id).first()
    if not character:
        logger.warning(
            "Character %s not found, skipping industry jobs sync", character_id
        )
        return
    if character.esi_suspended:
        logger.debug(
            "Skipping industry jobs for ESI suspended character %s",
            character_id,
        )
        return

    if not Token.get_token(character_id, [INDUSTRY_JOBS_SCOPE]):
        logger.debug(
            "No valid token with industry jobs scope for character %s",
            character_id,
        )
        return

    response = EsiClient(character_id).get_character_industry_jobs(
        include_completed=True
    )
    if not response.success():
        logger.error(
            "ESI error %s fetching industry jobs for character %s",
            response.response_code,
            character_id,
        )
        return

    jobs_data = response.data or []
    seen_job_ids = []

    for raw in jobs_data:
        job_id = raw["job_id"]
        seen_job_ids.append(job_id)
        completed_date = _parse_esi_date(raw.get("completed_date"))
        cost = raw.get("cost")
        if cost is not None:
            cost = Decimal(str(cost))

        IndustryJob.objects.update_or_create(
            job_id=job_id,
            defaults={
                "character_id": character.pk,
                "activity_id": raw["activity_id"],
                "blueprint_id": raw["blueprint_id"],
                "blueprint_type_id": raw["blueprint_type_id"],
                "blueprint_location_id": raw["blueprint_location_id"],
                "facility_id": raw["facility_id"],
                "location_id": raw["location_id"],
                "output_location_id": raw["output_location_id"],
                "status": raw["status"],
                "installer_id": raw["installer_id"],
                "start_date": _parse_esi_date(raw["start_date"]),
                "end_date": _parse_esi_date(raw["end_date"]),
                "duration": raw["duration"],
                "completed_date": completed_date,
                "completed_character_id": raw.get("completed_character_id"),
                "runs": raw["runs"],
                "licensed_runs": raw.get("licensed_runs", 0),
                "cost": cost,
            },
        )

    # Mark jobs we no longer see (cancelled or expired from ESI cache) - optional:
    # we could delete old completed/cancelled instead. For simplicity we leave
    # existing DB rows as-is; they keep their last known state.
    logger.info(
        "Synced %s industry job(s) for character %s",
        len(seen_job_ids),
        character_id,
    )
