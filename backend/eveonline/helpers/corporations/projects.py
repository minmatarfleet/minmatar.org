"""Mirror a corporation's in-game projects from ESI.

ESI only reads projects: a corporation creates and funds them in game. The
listing is cheap (one cursor walk), so every sync walks it; the detail and
contributor calls only run for projects whose ``last_modified`` moved.
"""

import logging

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from eveuniverse.models import (
    EveConstellation,
    EveFaction,
    EveGroup,
    EveRegion,
    EveSolarSystem,
    EveType,
)

from eveonline.client import SCOPE_CORPORATION_PROJECTS, esi_for
from eveonline.helpers.corporations.update import get_director_with_scope
from eveonline.helpers.esi import parse_esi_date
from eveonline.models import (
    EveAlliance,
    EveCorporation,
    EveCorporationProject,
    EveCorporationProjectContributor,
)

logger = logging.getLogger(__name__)

# ESI answers these when we are over a limit; stop the run, don't spend more.
RATE_LIMITED = (420, 429)
DELETED = "Deleted"
ACTIVE = "Active"

SYNCED_KEY = "corporation_projects:synced:{}"
REFRESHING_KEY = "corporation_projects:refreshing:{}"
SYNCED_TTL = 30 * 24 * 3600
# A manual refresh waits this long before another one is queued.
REFRESH_COOLDOWN_SECONDS = 120

# Configuration keys whose entries name something we can look up locally.
TARGET_KINDS = (
    "locations",
    "ships",
    "factions",
    "identities",
    "items",
    "materials",
    "corporations",
)


def projects_scope_holder(corporation: EveCorporation):
    """The CEO or director whose token can read projects, or None."""
    return get_director_with_scope(corporation, SCOPE_CORPORATION_PROJECTS)


def last_synced(corporation_id: int):
    return cache.get(SYNCED_KEY.format(corporation_id))


def is_refreshing(corporation_id: int) -> bool:
    return bool(cache.get(REFRESHING_KEY.format(corporation_id)))


def mark_refreshing(corporation_id: int) -> bool:
    """Claim a manual refresh. False while the last one is cooling down."""
    return cache.add(
        REFRESHING_KEY.format(corporation_id), 1, REFRESH_COOLDOWN_SECONDS
    )


def sync_corporation_projects(corporation_id: int) -> str:
    """Fetch the corporation's projects and store what changed.

    Returns a short status: ``ok``, ``no_corporation``, ``no_token`` or
    ``esi_error``.
    """
    corporation = (
        EveCorporation.objects.select_related("ceo")
        .prefetch_related("directors")
        .filter(corporation_id=corporation_id)
        .first()
    )
    if corporation is None:
        return "no_corporation"
    try:
        holder = projects_scope_holder(corporation)
        if holder is None:
            return "no_token"
        return _sync(corporation, esi_for(holder))
    finally:
        cache.delete(REFRESHING_KEY.format(corporation_id))


def _sync(corporation: EveCorporation, esi) -> str:
    listing = esi.get_corporation_projects(corporation.corporation_id)
    if not listing.success():
        logger.warning(
            "ESI %s listing projects for %s (%s)",
            listing.response_code,
            corporation.name,
            corporation.corporation_id,
        )
        return "esi_error"

    known = {
        str(project.project_id): project
        for project in EveCorporationProject.objects.filter(
            corporation=corporation
        )
    }
    for row in listing.results() or []:
        existing = known.get(row.get("id"))
        seen = existing.last_modified if existing else None
        project = _save_summary(corporation, row, existing)
        if project is None or not _needs_detail(project, seen):
            continue
        status = _sync_detail(esi, corporation, project)
        if status in RATE_LIMITED:
            logger.warning(
                "ESI %s on project detail for %s; stopping this run",
                status,
                corporation.corporation_id,
            )
            return "esi_error"

    cache.set(
        SYNCED_KEY.format(corporation.corporation_id),
        timezone.now(),
        SYNCED_TTL,
    )
    return "ok"


def _needs_detail(project: EveCorporationProject, seen) -> bool:
    """New, never fully fetched, or modified since the last listing."""
    if project.state == DELETED:
        return False
    return (
        seen is None
        or project.detail_synced_at is None
        or project.last_modified != seen
    )


def _save_summary(corporation, row: dict, existing):
    """Upsert the fields the listing carries. Returns the saved project."""
    project_id = row.get("id")
    last_modified = parse_esi_date(row.get("last_modified"))
    if not project_id or last_modified is None:
        return None
    progress = row.get("progress") or {}
    reward = row.get("reward") or {}
    fields = {
        "corporation": corporation,
        "name": (row.get("name") or "")[:255],
        "state": row.get("state") or "",
        "last_modified": last_modified,
        "progress_current": progress.get("current") or 0,
        "progress_desired": progress.get("desired") or 0,
    }
    if reward:
        fields["reward_initial"] = reward.get("initial")
        fields["reward_remaining"] = reward.get("remaining")
    if existing is None:
        return EveCorporationProject.objects.create(
            project_id=project_id, **fields
        )
    for name, value in fields.items():
        setattr(existing, name, value)
    existing.save()
    return existing


def _sync_detail(esi, corporation, project: EveCorporationProject) -> int:
    """Fetch detail and contributors. Returns 0 or the failing status."""
    corporation_id = corporation.corporation_id
    detail = esi.get_corporation_project(corporation_id, project.project_id)
    if not detail.success():
        project.detail_synced_at = None
        project.save(update_fields=["detail_synced_at"])
        logger.info(
            "ESI %s on project %s detail", detail.response_code, project.pk
        )
        return detail.response_code
    apply_detail(project, detail.results() or {})

    contributors = esi.get_corporation_project_contributors(
        corporation_id, project.project_id
    )
    if not contributors.success():
        # Keep the old rows and fetch again on the next run.
        project.detail_synced_at = None
        project.save()
        logger.info(
            "ESI %s on project %s contributors",
            contributors.response_code,
            project.pk,
        )
        return contributors.response_code
    with transaction.atomic():
        replace_contributors(project, contributors.results() or [])
        project.detail_synced_at = timezone.now()
        project.save()
    return 0


def apply_detail(project: EveCorporationProject, detail: dict) -> None:
    """Copy the detail call's fields onto the project (not saved)."""
    details = detail.get("details") or {}
    creator = detail.get("creator") or {}
    contribution = detail.get("contribution") or {}
    progress = detail.get("progress") or {}
    reward = detail.get("reward") or {}
    kind, configuration = split_configuration(detail.get("configuration"))

    project.name = (detail.get("name") or project.name)[:255]
    project.state = detail.get("state") or project.state
    project.description = details.get("description") or ""
    project.career = details.get("career") or ""
    project.created = parse_esi_date(details.get("created"))
    project.expires = parse_esi_date(details.get("expires"))
    project.finished = parse_esi_date(details.get("finished"))
    project.creator_id = creator.get("id")
    project.creator_name = creator.get("name") or ""
    project.kind = kind
    project.configuration = configuration
    project.targets = resolve_targets(configuration)
    project.reward_per_contribution = contribution.get(
        "reward_per_contribution"
    )
    project.participation_limit = contribution.get("participation_limit")
    project.submission_limit = contribution.get("submission_limit")
    project.submission_multiplier = contribution.get("submission_multiplier")
    if progress:
        project.progress_current = progress.get("current") or 0
        project.progress_desired = progress.get("desired") or 0
    if reward:
        project.reward_initial = reward.get("initial")
        project.reward_remaining = reward.get("remaining")
    if detail.get("last_modified"):
        project.last_modified = parse_esi_date(detail["last_modified"])


def split_configuration(configuration) -> tuple[str, dict]:
    """``{"destroy_ship": {...}}`` -> ``("destroy_ship", {...})``."""
    if not isinstance(configuration, dict) or not configuration:
        return "", {}
    kind, inner = next(iter(configuration.items()))
    if kind == "unknown" and isinstance(inner, dict):
        return str(inner.get("type") or "unknown")[:32], inner
    return kind[:32], inner if isinstance(inner, dict) else {}


def replace_contributors(project, rows: list[dict]) -> None:
    by_character = {}
    for row in rows:
        character_id = row.get("id")
        if character_id is None:
            continue
        by_character[character_id] = EveCorporationProjectContributor(
            project=project,
            character_id=character_id,
            character_name=(row.get("name") or "")[:255],
            contributed=row.get("contributed") or 0,
        )
    EveCorporationProjectContributor.objects.filter(project=project).delete()
    EveCorporationProjectContributor.objects.bulk_create(by_character.values())


def _names(model, ids, pk="id", name="name") -> list[str]:
    if not ids:
        return []
    found = dict(
        model.objects.filter(**{f"{pk}__in": ids}).values_list(pk, name)
    )
    return [found[i] for i in ids if i in found]


def _entity_names(entries: list) -> list[str]:
    """Names for a list of one-key entries like ``{"type_id": 587}``.

    Only local tables are read; anything we have never seen is left out
    rather than fetched from ESI on a page load or a sync.
    """
    ids = {}
    for entry in entries or []:
        if isinstance(entry, dict) and len(entry) == 1:
            key, value = next(iter(entry.items()))
            ids.setdefault(key, []).append(value)
    names = []
    names += _names(EveSolarSystem, ids.get("solar_system_id"))
    names += _names(EveConstellation, ids.get("constellation_id"))
    names += _names(EveRegion, ids.get("region_id"))
    names += _names(EveType, ids.get("type_id"))
    names += _names(EveGroup, ids.get("group_id"))
    names += _names(EveFaction, ids.get("faction_id"))
    names += _names(
        EveCorporation,
        ids.get("corporation_id"),
        pk="corporation_id",
    )
    names += _names(EveAlliance, ids.get("alliance_id"), pk="alliance_id")
    return names


def resolve_targets(configuration: dict) -> list[dict]:
    targets = []
    for kind in TARGET_KINDS:
        entries = configuration.get(kind)
        if not entries:
            continue
        names = _entity_names(entries)
        if names:
            targets.append({"kind": kind, "names": names})
    return targets


def project_out(project: EveCorporationProject, campaigns=None) -> dict:
    """The API shape of a project; ``contributors`` must be prefetched.

    ``campaigns`` is the list of campaigns it is attached to, if wanted.
    """
    corporation = project.corporation
    return {
        "project_id": str(project.project_id),
        "corporation_id": corporation.corporation_id,
        "corporation_name": corporation.name,
        "name": project.name,
        "description": project.description,
        "state": project.state,
        "kind": project.kind,
        "targets": project.targets or [],
        "creator_id": project.creator_id,
        "creator_name": project.creator_name,
        "progress_current": project.progress_current,
        "progress_desired": project.progress_desired,
        "reward_initial": project.reward_initial,
        "reward_remaining": project.reward_remaining,
        "reward_per_contribution": project.reward_per_contribution,
        "participation_limit": project.participation_limit,
        "created": project.created,
        "expires": project.expires,
        "finished": project.finished,
        "last_modified": project.last_modified,
        "contributors": [
            {
                "character_id": row.character_id,
                "character_name": row.character_name,
                "contributed": row.contributed,
            }
            for row in project.contributors.all()
        ],
        "campaigns": campaigns or [],
    }
