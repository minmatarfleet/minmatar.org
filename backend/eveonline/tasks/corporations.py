import logging

from app.celery import app
from eveonline.helpers.corporations import (
    SCOPE_CORPORATION_BLUEPRINTS,
    SCOPE_CORPORATION_CONTRACTS,
    SCOPE_CORPORATION_INDUSTRY_JOBS,
    SCOPE_CORPORATION_MEMBERSHIP,
    get_director_with_scope,
    sync_alliance_corporations_from_esi,
    update_corporation_blueprints as refresh_corporation_blueprints,
    update_corporation_contracts as refresh_corporation_contracts,
    update_corporation_industry_jobs as refresh_corporation_industry_jobs,
    update_corporation_members_and_roles as refresh_corporation_members_and_roles,
    update_corporation_populate as refresh_corporation_populate,
)
from eveonline.models import EveCorporation

logger = logging.getLogger(__name__)

ALLIED_ALLIANCE_NAMES = [
    "Minmatar Fleet Alliance",
    "Minmatar Fleet Associates",
]


@app.task
def update_corporations():
    """Queue update_corporation for each allied corporation."""
    for corporation in EveCorporation.objects.filter(
        alliance__name__in=ALLIED_ALLIANCE_NAMES
    ):
        update_corporation.apply_async(args=[corporation.corporation_id])


@app.task
def sync_alliance_corporations():
    """
    For each EveAlliance, fetch corporation IDs from ESI, get_or_create
    EveCorporation for each, and populate new ones. Returns number created.
    """
    total_created = sync_alliance_corporations_from_esi()
    logger.info(
        "sync_alliance_corporations complete: %d new corporations created",
        total_created,
    )
    return total_created


@app.task(rate_limit="1/m")
def update_corporation(corporation_id):
    """Update a corporation's public info and, when a director has scope, members/roles, contracts, industry jobs."""
    corporation = EveCorporation.objects.filter(
        corporation_id=corporation_id
    ).first()
    if not corporation:
        logger.warning("Corporation %s not found", corporation_id)
        return
    logger.info(
        "Updating corporation %s (%s)",
        corporation.name or corporation_id,
        corporation_id,
    )
    refresh_corporation_populate(corporation_id)
    corporation = EveCorporation.objects.filter(
        corporation_id=corporation_id
    ).first()
    if not corporation:
        return
    if (
        corporation.active
        and corporation.type in ["alliance", "associate"]
        and get_director_with_scope(corporation, SCOPE_CORPORATION_MEMBERSHIP)
    ):
        refresh_corporation_members_and_roles(corporation_id)
    if get_director_with_scope(corporation, SCOPE_CORPORATION_CONTRACTS):
        refresh_corporation_contracts(corporation_id)
    if get_director_with_scope(corporation, SCOPE_CORPORATION_INDUSTRY_JOBS):
        refresh_corporation_industry_jobs(corporation_id)
    if get_director_with_scope(corporation, SCOPE_CORPORATION_BLUEPRINTS):
        refresh_corporation_blueprints(corporation_id)
