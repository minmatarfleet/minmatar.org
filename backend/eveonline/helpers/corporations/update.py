"""Helpers to update a corporation's ESI-derived data (public info, members, roles, contracts, industry jobs)."""

import logging
from datetime import datetime
from decimal import Decimal

import pytz
from django.utils import timezone
from esi.models import Token

from eveonline.client import EsiClient
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCorporation,
    EveCorporationBlueprint,
    EveCorporationContract,
    EveCorporationIndustryJob,
)

logger = logging.getLogger(__name__)

SCOPE_CORPORATION_MEMBERSHIP = [
    "esi-corporations.read_corporation_membership.v1"
]
SCOPE_CORPORATION_CONTRACTS = ["esi-contracts.read_corporation_contracts.v1"]
SCOPE_CHARACTER_CONTRACTS = ["esi-contracts.read_character_contracts.v1"]
SCOPE_CORPORATION_INDUSTRY_JOBS = ["esi-industry.read_corporation_jobs.v1"]
SCOPE_CORPORATION_BLUEPRINTS = ["esi-corporations.read_blueprints.v1"]
CONTRACT_FETCH_SPREAD_SECONDS = 4 * 3600  # 4 hours


def alliance_corporation_ids():
    """Corporation IDs for all corporations in tracked alliances."""
    return set(
        EveCorporation.objects.filter(
            alliance__in=EveAlliance.objects.all()
        ).values_list("corporation_id", flat=True)
    )


def get_character_with_contract_scope_for_corporation(
    corporation_id: int,
) -> int | None:
    """
    Return a character_id in this corporation with a valid token that has
    corporation contract scope, or None if none found.
    """
    for character in (
        EveCharacter.objects.filter(corporation_id=corporation_id)
        .exclude(token__isnull=True)
        .exclude(esi_suspended=True)
    ):
        if Token.get_token(
            character.character_id, SCOPE_CORPORATION_CONTRACTS
        ):
            return character.character_id
    return None


def known_contract_issuer_ids():
    """Set of issuer IDs we consider 'known' (alliance characters + alliance corps)."""
    alliance_ids = set(
        EveAlliance.objects.values_list("alliance_id", flat=True)
    )
    character_ids = set(
        EveCharacter.objects.filter(alliance_id__in=alliance_ids).values_list(
            "character_id", flat=True
        )
    )
    corp_ids = alliance_corporation_ids()
    return character_ids | corp_ids


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


def get_director_with_scope(corporation, scope_list):
    """
    Return a corporation director or CEO that has a valid token with the given
    scope, or None. Checks CEO first, then directors.
    """
    candidate_ids = set()
    if corporation.ceo_id:
        candidate_ids.add(corporation.ceo.character_id)
    for director in corporation.directors.all():
        candidate_ids.add(director.character_id)
    for character_id in candidate_ids:
        if Token.get_token(character_id, scope_list):
            return EveCharacter.objects.get(character_id=character_id)
    return None


def sync_alliance_corporations_from_esi() -> int:
    """
    For each EveAlliance, fetch corporation IDs from ESI, get_or_create
    EveCorporation for each, and populate new ones. Returns number created.
    Uses public ESI (no token required).
    """
    alliances = EveAlliance.objects.all().order_by("alliance_id")
    logger.info("Syncing corporations for %d alliances", alliances.count())
    total_created = 0
    for alliance in alliances:
        esi_response = EsiClient(None).get_alliance_corporations(
            alliance.alliance_id
        )
        if not esi_response.success():
            logger.warning(
                "ESI error %d fetching corporations for alliance %s (%s)",
                esi_response.response_code,
                alliance.name or alliance.alliance_id,
                alliance.alliance_id,
            )
            continue
        corporation_ids = esi_response.results() or []
        logger.info(
            "Alliance %s (%s): %d corporations from ESI",
            alliance.name or alliance.alliance_id,
            alliance.alliance_id,
            len(corporation_ids),
        )
        for corporation_id in corporation_ids:
            corporation, created = EveCorporation.objects.get_or_create(
                corporation_id=corporation_id
            )
            if created:
                update_corporation_populate(corporation_id)
                corporation.refresh_from_db()
                total_created += 1
                logger.info(
                    "Created corporation %s (%s)",
                    corporation.name,
                    corporation_id,
                )
    return total_created


def _all_roles_for_member(role_data):
    """Collect all role names for a member from ESI role entry (base, hq, other)."""
    all_roles = set(role_data.get("roles") or [])
    for key in ("roles_at_base", "roles_at_hq", "roles_at_other"):
        all_roles.update(role_data.get(key) or [])
    return all_roles


def update_corporation_populate(corporation_id: int) -> None:
    """Fetch public corporation details from ESI and save. May delete corp if NPC."""
    corporation = EveCorporation.objects.filter(
        corporation_id=corporation_id
    ).first()
    if not corporation:
        logger.warning(
            "Corporation %s not found, skipping populate", corporation_id
        )
        return
    corporation.populate()


def update_corporation_members_and_roles(corporation_id: int) -> None:
    """
    Sync corporation member list (create missing EveCharacters) and set
    directors/recruiters/stewards from ESI. Only runs for active alliance/associate
    corps when a director (or CEO) has a token with
    esi-corporations.read_corporation_membership.v1.
    """
    corporation = EveCorporation.objects.filter(
        corporation_id=corporation_id
    ).first()
    if not corporation:
        logger.debug(
            "Corporation %s not found, skipping members/roles", corporation_id
        )
        return
    if not corporation.active or corporation.type not in [
        "alliance",
        "associate",
    ]:
        logger.debug(
            "Corporation %s (%s) not active or not alliance/associate, skipping members/roles",
            corporation.name,
            corporation_id,
        )
        return
    character = get_director_with_scope(
        corporation, SCOPE_CORPORATION_MEMBERSHIP
    )
    if not character:
        logger.debug(
            "No director with %s for corporation %s (%s), skipping members/roles",
            SCOPE_CORPORATION_MEMBERSHIP[0],
            corporation.name,
            corporation_id,
        )
        return

    esi_members = EsiClient(character).get_corporation_members(
        corporation.corporation_id
    )
    if not esi_members.success():
        logger.warning(
            "ESI error %s fetching members for corporation %s (%s)",
            esi_members.response_code,
            corporation.name,
            corporation_id,
        )
        return

    for member_id in esi_members.results():
        if not EveCharacter.objects.filter(character_id=member_id).exists():
            logger.info(
                "Creating character %s for corporation %s",
                member_id,
                corporation.name,
            )
            EveCharacter.objects.create(character_id=member_id)

    esi_roles = EsiClient(character).get_corporation_roles(
        corporation.corporation_id
    )
    if not esi_roles.success():
        logger.warning(
            "ESI error %s fetching roles for corporation %s (%s)",
            esi_roles.response_code,
            corporation.name,
            corporation_id,
        )
        return

    roles_data = esi_roles.results() or []
    director_ids = []
    recruiter_ids = []
    steward_ids = []
    for entry in roles_data:
        char_id = entry.get("character_id")
        if char_id is None:
            continue
        all_roles = _all_roles_for_member(entry)
        char, _ = EveCharacter.objects.get_or_create(
            character_id=char_id, defaults={}
        )
        if "Director" in all_roles:
            director_ids.append(char.id)
        if "Personnel_Manager" in all_roles:
            recruiter_ids.append(char.id)
        if "Station_Manager" in all_roles:
            steward_ids.append(char.id)
    corporation.directors.set(EveCharacter.objects.filter(id__in=director_ids))
    corporation.recruiters.set(
        EveCharacter.objects.filter(id__in=recruiter_ids)
    )
    corporation.stewards.set(EveCharacter.objects.filter(id__in=steward_ids))


def update_corporation_contracts(corporation_id: int) -> int:
    """
    Sync corporation contracts from ESI into EveCorporationContract. Only runs
    when a director (or CEO) has a token with
    esi-contracts.read_corporation_contracts.v1. Returns count synced.
    """
    corporation = EveCorporation.objects.filter(
        corporation_id=corporation_id
    ).first()
    if not corporation:
        logger.debug(
            "Corporation %s not found, skipping contracts", corporation_id
        )
        return 0
    character = get_director_with_scope(
        corporation, SCOPE_CORPORATION_CONTRACTS
    )
    if not character:
        logger.debug(
            "No director with %s for corporation %s (%s), skipping contracts",
            SCOPE_CORPORATION_CONTRACTS[0],
            corporation.name,
            corporation_id,
        )
        return 0

    response = EsiClient(character).get_corporation_contracts(
        corporation.corporation_id
    )
    if not response.success():
        logger.warning(
            "ESI error %s fetching contracts for corporation %s (%s)",
            response.response_code,
            corporation.name,
            corporation_id,
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

        EveCorporationContract.objects.update_or_create(
            contract_id=contract_id,
            defaults={
                "corporation_id": corporation.pk,
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
        "Synced %s contract(s) for corporation %s (%s)",
        len(contracts_data),
        corporation.name,
        corporation_id,
    )
    return len(contracts_data)


def update_corporation_industry_jobs(corporation_id: int) -> int:
    """
    Sync corporation industry jobs from ESI into EveCorporationIndustryJob.
    Only runs when a director (or CEO) has a token with
    esi-industry.read_corporation_jobs.v1. Returns count synced.
    """
    corporation = EveCorporation.objects.filter(
        corporation_id=corporation_id
    ).first()
    if not corporation:
        logger.debug(
            "Corporation %s not found, skipping industry jobs", corporation_id
        )
        return 0
    character = get_director_with_scope(
        corporation, SCOPE_CORPORATION_INDUSTRY_JOBS
    )
    if not character:
        logger.debug(
            "No director with %s for corporation %s (%s), skipping industry jobs",
            SCOPE_CORPORATION_INDUSTRY_JOBS[0],
            corporation.name,
            corporation_id,
        )
        return 0

    response = EsiClient(character).get_corporation_industry_jobs(
        corporation.corporation_id, include_completed=True
    )
    if not response.success():
        logger.warning(
            "ESI error %s fetching industry jobs for corporation %s (%s)",
            response.response_code,
            corporation.name,
            corporation_id,
        )
        return 0

    jobs_data = response.results() or []
    for raw in jobs_data:
        job_id = raw["job_id"]
        completed_date = _parse_esi_date(raw.get("completed_date"))
        cost = raw.get("cost")
        if cost is not None:
            cost = Decimal(str(cost))
        # ESI uses station_id for corporation jobs too
        location_id = raw.get("station_id", raw.get("location_id"))

        EveCorporationIndustryJob.objects.update_or_create(
            job_id=job_id,
            defaults={
                "corporation_id": corporation.pk,
                "activity_id": raw["activity_id"],
                "blueprint_id": raw["blueprint_id"],
                "blueprint_type_id": raw["blueprint_type_id"],
                "blueprint_location_id": raw["blueprint_location_id"],
                "facility_id": raw["facility_id"],
                "location_id": location_id,
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
    logger.info(
        "Synced %s industry job(s) for corporation %s (%s)",
        len(jobs_data),
        corporation.name,
        corporation_id,
    )
    return len(jobs_data)


def update_corporation_blueprints(corporation_id: int) -> int:
    """Fetch corporation blueprints from ESI and replace. Returns count synced."""
    corporation = (
        EveCorporation.objects.filter(corporation_id=corporation_id)
    ).first()
    if not corporation:
        logger.warning(
            "Corporation %s not found, skipping blueprints sync",
            corporation_id,
        )
        return 0

    character = get_director_with_scope(
        corporation, SCOPE_CORPORATION_BLUEPRINTS
    )
    if not character:
        logger.debug(
            "No director with %s for corporation %s (%s), skipping blueprints",
            SCOPE_CORPORATION_BLUEPRINTS[0],
            corporation.name,
            corporation_id,
        )
        return 0

    response = EsiClient(character).get_corporation_blueprints(
        corporation.corporation_id
    )
    if not response.success():
        logger.warning(
            "ESI error %s fetching blueprints for corporation %s (%s)",
            response.response_code,
            corporation.name,
            corporation_id,
        )
        return 0

    blueprints_data = response.results() or []
    EveCorporationBlueprint.objects.filter(corporation=corporation).delete()
    for raw in blueprints_data:
        EveCorporationBlueprint.objects.create(
            corporation=corporation,
            item_id=raw["item_id"],
            type_id=raw["type_id"],
            location_id=raw["location_id"],
            location_flag=raw["location_flag"],
            material_efficiency=raw["material_efficiency"],
            time_efficiency=raw["time_efficiency"],
            quantity=raw["quantity"],
            runs=raw["runs"],
        )
    logger.info(
        "Synced %s blueprint(s) for corporation %s (%s)",
        len(blueprints_data),
        corporation.name,
        corporation_id,
    )
    return len(blueprints_data)
