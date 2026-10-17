"""Helpers to update a character's ESI-derived data (assets, skills, killmails, contracts, industry jobs)."""

import logging
import time
from datetime import datetime
from decimal import Decimal

import pytz
from django.db import transaction
from django.utils import timezone

from eveonline.client import EsiClient
from eveonline.models import (
    EveCharacter,
    EveCharacterBlueprint,
    EveCharacterContract,
    EveCharacterIndustryJob,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
    EveSkillset,
)

from eveonline.helpers.characters.assets import create_character_assets
from eveonline.helpers.db_sync import replace_with_bulk_create
from eveonline.helpers.characters.skills import (
    create_eve_character_skillset,
    upsert_character_skills,
)

logger = logging.getLogger(__name__)


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


def update_character_assets(eve_character_id: int) -> tuple[int, int, int]:
    """Fetch assets from ESI and replace character's assets. Returns (created, updated, deleted)."""
    start = time.perf_counter()
    character = EveCharacter.objects.get(character_id=eve_character_id)
    logger.debug("Updating assets for character %s", eve_character_id)

    response = EsiClient(character).get_character_assets()
    if not response.success():
        # Expected ESI/token failures (opaque 906, suspended, missing token)
        # are per-character and should not dominate Sentry as errors.
        log = (
            logger.warning
            if response.response_code in (902, 904, 905, 906)
            else logger.error
        )
        log(
            "Error %s fetching assets for %s",
            response.error_text(),
            character.summary(),
        )
        return 0, 0, 0

    fetch_time = time.perf_counter() - start
    created, updated, deleted = create_character_assets(
        character, response.results()
    )
    elapsed = time.perf_counter() - start
    logger.info(
        "Updated assets for %s in %.6f (%.6f) seconds (%d, %d, %d)",
        character.character_name,
        elapsed,
        fetch_time,
        created,
        updated,
        deleted,
    )
    return created, updated, deleted


def update_character_skills(eve_character_id: int) -> None:
    """Update skills and skillsets for a character."""
    character = EveCharacter.objects.get(character_id=eve_character_id)
    if character.esi_suspended:
        logger.info(
            "Skipping skills update for character %s", eve_character_id
        )
        return

    logger.info("Updating skills for character %s", eve_character_id)
    upsert_character_skills(eve_character_id)
    for skillset in EveSkillset.objects.all():
        create_eve_character_skillset(eve_character_id, skillset)


def _optional(row: dict, key: str):
    return row.get(key) if isinstance(row, dict) else None


def update_character_killmails(eve_character_id: int) -> None:
    """Fetch recent killmails from ESI and create missing records.

    Killmails already stored are skipped before their detail is fetched, so
    a sync only spends ESI calls on mails it has not seen.
    """
    character = EveCharacter.objects.get(character_id=eve_character_id)
    logger.info("Updating killmails for character %s", eve_character_id)
    esi = EsiClient(eve_character_id)

    response = esi.get_recent_killmails()
    if not response.success():
        logger.warning(
            "Skipping killmail update for character %s, %s",
            eve_character_id,
            response.response_code,
        )
        return

    recent = response.results() or []
    stored = set(
        EveCharacterKillmail.objects.filter(
            id__in=[killmail["killmail_id"] for killmail in recent]
        ).values_list("id", flat=True)
    )
    for killmail in recent:
        killmail_id = killmail["killmail_id"]
        if killmail_id in stored:
            continue
        response = esi.get_character_killmail(
            killmail_id, killmail["killmail_hash"]
        )
        if not response.success():
            logger.warning(
                "Skipping killmail %s for character %s: %s",
                killmail_id,
                eve_character_id,
                response.error_text(),
            )
            continue
        _store_character_killmail(
            character,
            killmail_id,
            killmail["killmail_hash"],
            response.results(),
        )
        stored.add(killmail_id)


def _store_character_killmail(
    character: EveCharacter, killmail_id: int, killmail_hash: str, details
) -> None:
    """One killmail and its attacker rows, written together."""
    victim = details["victim"]
    attackers = details["attackers"]
    with transaction.atomic():
        killmail_obj = EveCharacterKillmail.objects.create(
            id=killmail_id,
            killmail_id=killmail_id,
            killmail_hash=killmail_hash,
            solar_system_id=details["solar_system_id"],
            ship_type_id=victim["ship_type_id"],
            killmail_time=details["killmail_time"],
            victim_character_id=victim.get("character_id"),
            victim_corporation_id=victim.get("corporation_id"),
            victim_alliance_id=victim.get("alliance_id"),
            victim_faction_id=victim.get("faction_id"),
            attackers=attackers,
            items=victim["items"],
            character=character,
        )
        EveCharacterKillmailAttacker.objects.bulk_create(
            [
                EveCharacterKillmailAttacker(
                    killmail=killmail_obj,
                    character_id=_optional(attacker, "character_id"),
                    corporation_id=_optional(attacker, "corporation_id"),
                    alliance_id=_optional(attacker, "alliance_id"),
                    faction_id=_optional(attacker, "faction_id"),
                    ship_type_id=_optional(attacker, "ship_type_id"),
                )
                for attacker in attackers or []
            ]
        )


def update_character_contracts(eve_character_id: int) -> int:
    """Fetch contracts from ESI and upsert EveCharacterContract. Returns count synced."""
    character = EveCharacter.objects.filter(
        character_id=eve_character_id
    ).first()
    if not character:
        logger.warning(
            "Character %s not found, skipping contracts sync", eve_character_id
        )
        return 0
    if character.esi_suspended:
        logger.debug(
            "Skipping contracts for ESI suspended character %s",
            eve_character_id,
        )
        return 0

    response = EsiClient(character).get_character_contracts()
    if not response.success():
        logger.warning(
            "Skipping contracts for character %s, %s",
            eve_character_id,
            response.response_code,
        )
        return 0

    contracts_data = response.results() or []
    for raw in contracts_data:
        contract_id = raw["contract_id"]
        price = raw.get("price")
        if price is not None:
            price = Decimal(str(price))
        reward = raw.get("reward")
        if reward is not None:
            reward = Decimal(str(reward))
        collateral = raw.get("collateral")
        if collateral is not None:
            collateral = Decimal(str(collateral))
        buyout = raw.get("buyout")
        if buyout is not None:
            buyout = Decimal(str(buyout))
        volume = raw.get("volume")
        if volume is not None:
            volume = Decimal(str(volume))

        EveCharacterContract.objects.update_or_create(
            contract_id=contract_id,
            defaults={
                "character_id": character.pk,
                "type": raw.get("type", ""),
                "status": raw.get("status", ""),
                "availability": raw.get("availability", ""),
                "issuer_id": raw.get("issuer_id"),
                "issuer_corporation_id": raw.get("issuer_corporation_id"),
                "assignee_id": raw.get("assignee_id"),
                "acceptor_id": raw.get("acceptor_id"),
                "for_corporation": raw.get("for_corporation", False),
                "date_issued": _parse_esi_date(raw.get("date_issued")),
                "date_expired": _parse_esi_date(raw.get("date_expired")),
                "date_accepted": _parse_esi_date(raw.get("date_accepted")),
                "date_completed": _parse_esi_date(raw.get("date_completed")),
                "days_to_complete": raw.get("days_to_complete"),
                "price": price,
                "reward": reward,
                "collateral": collateral,
                "buyout": buyout,
                "volume": volume,
                "start_location_id": raw.get("start_location_id"),
                "end_location_id": raw.get("end_location_id"),
                "title": raw.get("title", ""),
            },
        )
    logger.info(
        "Synced %s contract(s) for character %s",
        len(contracts_data),
        eve_character_id,
    )
    return len(contracts_data)


def update_character_industry_jobs(
    eve_character_id: int,
) -> tuple[int, list[int]]:
    """
    Fetch industry jobs from ESI and upsert EveCharacterIndustryJob.

    Returns (count synced, list of newly created ESI job_ids).
    """
    character = EveCharacter.objects.filter(
        character_id=eve_character_id
    ).first()
    if not character:
        logger.warning(
            "Character %s not found, skipping industry jobs sync",
            eve_character_id,
        )
        return 0, []
    if character.esi_suspended:
        logger.debug(
            "Skipping industry jobs for ESI suspended character %s",
            eve_character_id,
        )
        return 0, []

    response = EsiClient(character).get_character_industry_jobs(
        include_completed=True
    )
    if not response.success():
        logger.warning(
            "Skipping industry jobs for character %s, %s",
            eve_character_id,
            response.response_code,
        )
        return 0, []

    jobs_data = response.results() or []
    created_job_ids: list[int] = []
    for raw in jobs_data:
        job_id = raw["job_id"]
        completed_date = _parse_esi_date(raw.get("completed_date"))
        cost = raw.get("cost")
        if cost is not None:
            cost = Decimal(str(cost))

        job, created = EveCharacterIndustryJob.objects.update_or_create(
            job_id=job_id,
            defaults={
                "character_id": character.pk,
                "activity_id": raw["activity_id"],
                "blueprint_id": raw["blueprint_id"],
                "blueprint_type_id": raw["blueprint_type_id"],
                "blueprint_location_id": raw["blueprint_location_id"],
                "facility_id": raw["facility_id"],
                "location_id": raw["station_id"],
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
        if created:
            created_job_ids.append(job.job_id)
    logger.info(
        "Synced %s industry job(s) for character %s",
        len(jobs_data),
        eve_character_id,
    )
    return len(jobs_data), created_job_ids


def update_character_blueprints(eve_character_id: int) -> int:
    """Fetch blueprints from ESI and replace character's blueprints. Returns count synced."""
    character = (
        EveCharacter.objects.filter(character_id=eve_character_id)
    ).first()
    if not character:
        logger.warning(
            "Character %s not found, skipping blueprints sync",
            eve_character_id,
        )
        return 0
    if character.esi_suspended:
        logger.debug(
            "Skipping blueprints for ESI suspended character %s",
            eve_character_id,
        )
        return 0

    response = EsiClient(character).get_character_blueprints()
    if not response.success():
        logger.warning(
            "Skipping blueprints for character %s, %s",
            eve_character_id,
            response.response_code,
        )
        return 0

    blueprints_data = response.results() or []
    instances = [
        EveCharacterBlueprint(
            character=character,
            item_id=raw["item_id"],
            type_id=raw["type_id"],
            location_id=raw["location_id"],
            location_flag=raw["location_flag"],
            material_efficiency=raw["material_efficiency"],
            time_efficiency=raw["time_efficiency"],
            quantity=raw["quantity"],
            runs=raw["runs"],
        )
        for raw in blueprints_data
    ]
    replace_with_bulk_create(
        delete_queryset=EveCharacterBlueprint.objects.filter(
            character=character
        ),
        instances=instances,
    )
    logger.info(
        "Synced %s blueprint(s) for character %s",
        len(blueprints_data),
        eve_character_id,
    )
    return len(blueprints_data)
