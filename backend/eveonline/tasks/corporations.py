import logging

from app.celery import app
from eveonline.helpers.corporations import (
    SCOPE_CORPORATION_BLUEPRINTS,
    SCOPE_CORPORATION_CONTRACTS,
    SCOPE_CORPORATION_INDUSTRY_JOBS,
    SCOPE_CORPORATION_MEMBERSHIP,
    SCOPE_CORPORATION_WALLET,
    resolve_directors_by_scope,
    sync_alliance_corporations_from_esi,
    update_corporation_blueprints as refresh_corporation_blueprints,
    update_corporation_contracts as refresh_corporation_contracts,
    update_corporation_industry_jobs as refresh_corporation_industry_jobs,
    update_corporation_members_and_roles as refresh_corporation_members_and_roles,
    update_corporation_populate as refresh_corporation_populate,
    update_corporation_wallet_journal as refresh_corporation_wallet_journal,
)
from eveonline.constants import ALLIED_ALLIANCE_NAMES
from eveonline.helpers.corporations import projects
from eveonline.models import EveCharacter, EveCorporation

logger = logging.getLogger(__name__)


@app.task
def update_corporations():
    """Queue update_corporation for each allied corporation."""
    for corporation in EveCorporation.objects.filter(
        alliance__name__in=ALLIED_ALLIANCE_NAMES
    ):
        update_corporation.apply_async(
            args=[corporation.corporation_id], queue="eveonline"
        )


@app.task
def sync_corporations_projects():
    """Queue a projects sync for each allied corporation."""
    for corporation_id in EveCorporation.objects.filter(
        alliance__name__in=ALLIED_ALLIANCE_NAMES
    ).values_list("corporation_id", flat=True):
        sync_corporation_projects.apply_async(
            args=[corporation_id], queue="eveonline"
        )


@app.task(rate_limit="20/m")
def sync_corporation_projects(corporation_id):
    """Mirror one corporation's in-game projects and their contributors."""
    status = projects.sync_corporation_projects(corporation_id)
    logger.info("Corporation %s projects sync: %s", corporation_id, status)
    return status


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


@app.task(rate_limit="10/m")
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
    corporation = (
        EveCorporation.objects.filter(corporation_id=corporation_id)
        .select_related("ceo")
        .prefetch_related("directors")
        .first()
    )
    if not corporation:
        return

    directors = resolve_directors_by_scope(
        corporation,
        [
            SCOPE_CORPORATION_MEMBERSHIP,
            SCOPE_CORPORATION_CONTRACTS,
            SCOPE_CORPORATION_INDUSTRY_JOBS,
            SCOPE_CORPORATION_BLUEPRINTS,
            SCOPE_CORPORATION_WALLET,
        ],
    )
    if (
        corporation.active
        and corporation.type in ["alliance", "associate"]
        and directors[tuple(SCOPE_CORPORATION_MEMBERSHIP)]
    ):
        refresh_corporation_members_and_roles(corporation_id)
    if directors[tuple(SCOPE_CORPORATION_CONTRACTS)]:
        refresh_corporation_contracts(corporation_id)
    if directors[tuple(SCOPE_CORPORATION_INDUSTRY_JOBS)]:
        refresh_corporation_industry_jobs(corporation_id)
    if directors[tuple(SCOPE_CORPORATION_BLUEPRINTS)]:
        refresh_corporation_blueprints(corporation_id)
    if directors[tuple(SCOPE_CORPORATION_WALLET)]:
        refresh_corporation_wallet_journal(corporation_id)


@app.task
def refresh_corporation_profile_stats(corporation_id=None):
    """Recompute cached public profile stats for one or all allied corps."""
    # Imported here to keep task module import light for Celery autodiscovery.
    from eveonline.helpers.corporations.stats_cache import (  # pylint: disable=import-outside-toplevel
        refresh_corporation_stats,
    )

    from eveonline.helpers.corporations.kills import (  # pylint: disable=import-outside-toplevel
        RecentKills,
    )

    corporations = EveCorporation.objects.all()
    if corporation_id is not None:
        corporations = corporations.filter(corporation_id=corporation_id)
    else:
        corporations = corporations.filter(
            alliance__name__in=ALLIED_ALLIANCE_NAMES
        )
    corporations = list(corporations)
    # One pass over recent killmails for every character involved, instead
    # of one per corporation.
    kills = RecentKills(
        EveCharacter.objects.filter(
            corporation_id__in=[c.corporation_id for c in corporations]
        ).values_list("character_id", flat=True)
    )
    refreshed = 0
    for corporation in corporations:
        try:
            refresh_corporation_stats(corporation, kills)
            refreshed += 1
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception(
                "Failed to refresh profile stats for corporation %s",
                corporation.corporation_id,
            )
    return refreshed
