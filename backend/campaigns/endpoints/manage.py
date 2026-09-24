"""Operator endpoints. A campaign runs with a name, systems and dates."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.endpoints.base import router
from campaigns.constants import STRUCTURE_TYPE_IDS
from campaigns.endpoints import schemas
from campaigns.endpoints import serializers
from campaigns.models import (
    AreaScope,
    Campaign,
    CampaignArea,
    CampaignKind,
    CampaignOpponent,
    CampaignStatus,
    CampaignSystem,
    CampaignWeekTarget,
    SystemGoal,
    SystemPriority,
    SystemRole,
)
from campaigns.services import plan
from campaigns.services import structures as structure_service
from feed.models import FeedMonitoredSystem
from groups.helpers.feature_access import can_use_feature, require_feature
from structures.helpers import get_skyhook_details, get_structure_details
from structures.models import EveStructureTimer

CREATE_FEATURE = "campaigns.create"
MANAGE_FEATURE = "campaigns.manage"
SCOUT_FEATURE = "structures.timers.manage"


def _can_manage(user, campaign: Campaign) -> bool:
    """Superusers, holders of the manage feature, and the creator.

    `is_staff` alone is deliberately not enough: it is a Django-admin login
    flag, not a campaigns role. The creator keeps manage rights on their own
    campaign only while they can still create campaigns at all.
    """
    if user.is_superuser:
        return True
    if require_feature(user, MANAGE_FEATURE) is None:
        return True
    return (
        campaign.created_by_id == user.id
        and require_feature(user, CREATE_FEATURE) is None
    )


def _can_scout(user, campaign: Campaign) -> bool:
    """Managers plus anyone who can submit structure timers (recon scouts)."""
    if _can_manage(user, campaign):
        return True
    return can_use_feature(user, SCOUT_FEATURE)


def _denied():
    return 403, {"detail": "feature_denied", "feature": MANAGE_FEATURE}


@router.post(
    "",
    response={
        200: schemas.CampaignCreated,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
)
def create_campaign(request, payload: schemas.CampaignCreateRequest):
    """Create a draft. Systems are named from the feed's monitored list."""
    denied = require_feature(request.user, CREATE_FEATURE)
    if denied:
        return denied

    if payload.end_at <= payload.start_at:
        return 400, {"detail": "end_at must be after start_at"}

    kind = payload.kind or CampaignKind.FACTION_WARFARE
    if kind == CampaignKind.FACTION_WARFARE and not payload.system_ids:
        return 400, {
            "detail": "faction_warfare campaigns need at least one system"
        }

    short_code = payload.short_code.upper()
    if Campaign.objects.filter(slug=payload.slug).exists():
        return 400, {"detail": f"slug {payload.slug} is already taken"}
    if Campaign.objects.filter(short_code=short_code).exists():
        return 400, {"detail": f"short code {short_code} is already taken"}

    known = dict(
        FeedMonitoredSystem.objects.filter(
            solar_system_id__in=payload.system_ids
        ).values_list("solar_system_id", "name")
    )
    unknown = [sid for sid in payload.system_ids if sid not in known]
    if unknown:
        return 400, {
            "detail": "unknown solar system ids: "
            + ", ".join(str(sid) for sid in unknown)
        }

    campaign = Campaign.objects.create(
        slug=payload.slug,
        short_code=short_code,
        name=payload.name,
        kind=kind,
        tagline=payload.tagline,
        description_md=payload.description_md,
        start_at=payload.start_at,
        end_at=payload.end_at,
        status=CampaignStatus.DRAFT,
        created_by=request.user,
    )

    for solar_system_id in payload.system_ids:
        CampaignSystem.objects.create(
            campaign=campaign,
            solar_system_id=solar_system_id,
            name=known[solar_system_id],
            is_fw_objective=True,
        )

    return {
        "slug": campaign.slug,
        "short_code": campaign.short_code,
        "name": campaign.name,
        "kind": campaign.kind,
        "status": campaign.status,
        "systems": [system.name for system in campaign.systems.all()],
    }


@router.patch(
    "/{slug}/systems/{system_id}",
    response={
        200: schemas.CampaignSystemSummary,
        400: ErrorResponse,
        403: ErrorResponse,
        404: None,
    },
    auth=AuthBearer(),
)
def patch_system(
    request,
    slug: str,
    system_id: int,
    payload: schemas.CampaignSystemPatch,
):
    """Mark a system as an FW objective or ops theater, and nudge goal/role."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    system = get_object_or_404(CampaignSystem, id=system_id, campaign=campaign)
    update_fields: list[str] = []
    if payload.is_fw_objective is not None:
        system.is_fw_objective = payload.is_fw_objective
        update_fields.append("is_fw_objective")
    if payload.goal is not None:
        if payload.goal not in SystemGoal.values:
            return 400, {"detail": f"unknown goal: {payload.goal}"}
        system.goal = payload.goal
        update_fields.append("goal")
    if payload.role is not None:
        if payload.role not in SystemRole.values:
            return 400, {"detail": f"unknown role: {payload.role}"}
        system.role = payload.role
        update_fields.append("role")
    if payload.priority is not None:
        if payload.priority not in SystemPriority.values:
            return 400, {"detail": f"unknown priority: {payload.priority}"}
        system.priority = payload.priority
        update_fields.append("priority")
    if update_fields:
        system.save(update_fields=update_fields)
    return serializers.system_summary(system, with_trend=False)


@router.post(
    "/{slug}/areas",
    response={
        200: schemas.CampaignAreaOut,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
)
def create_area(
    request, slug: str, payload: schemas.CampaignAreaCreateRequest
):
    """Add a constellation or region ops theater (guidance only)."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()

    if payload.scope == AreaScope.CONSTELLATION:
        if not payload.constellation_id:
            return 400, {"detail": "constellation_id required"}
        area, _ = CampaignArea.objects.update_or_create(
            campaign=campaign,
            scope=AreaScope.CONSTELLATION,
            constellation_id=payload.constellation_id,
            defaults={
                "name": payload.name,
                "region_id": None,
            },
        )
    else:
        if not payload.region_id:
            return 400, {"detail": "region_id required"}
        area, _ = CampaignArea.objects.update_or_create(
            campaign=campaign,
            scope=AreaScope.REGION,
            region_id=payload.region_id,
            defaults={
                "name": payload.name,
                "constellation_id": None,
            },
        )
    return serializers.area_out(area)


@router.delete(
    "/{slug}/areas/{area_id}",
    response={200: dict, 403: ErrorResponse, 404: None},
    auth=AuthBearer(),
)
def delete_area(request, slug: str, area_id: int):
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    area = get_object_or_404(CampaignArea, id=area_id, campaign=campaign)
    area.delete()
    return {"deleted": True}


@router.post(
    "/{slug}/week/propose",
    response={200: dict, 403: ErrorResponse},
    auth=AuthBearer(),
)
def propose_week(request, slug: str):
    """Re-run this week's proposal. Accepted targets are left alone."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    proposed = plan.propose_week(campaign)
    plan.update_week_progress(campaign)
    return {"proposed": proposed}


@router.patch(
    "/{slug}/week/{target_id}",
    response={200: schemas.WeekTargetOut, 403: ErrorResponse},
    auth=AuthBearer(),
)
def accept_week_target(
    request, slug: str, target_id: int, payload: schemas.WeekTargetPatch
):
    """Accept the proposal, or nudge the number. One click either way."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()

    row = get_object_or_404(
        CampaignWeekTarget, id=target_id, campaign_system__campaign=campaign
    )
    # Touching the number at all makes it the operator's, or the next
    # proposal would quietly overwrite what they just typed.
    row.target = payload.target
    row.proposed = False
    row.accepted_by = request.user
    row.accepted_at = timezone.now()
    row.save()

    return {
        "id": row.id,
        "system": row.campaign_system.name,
        "system_id": row.campaign_system_id,
        "goal": row.campaign_system.goal,
        "metric": row.metric,
        "target": row.target,
        "progress": row.progress,
        "pace_expected": row.pace_expected,
        "baseline": row.baseline,
        "pace": row.pace,
        "proposed": row.proposed,
        "last_week_actual": row.last_week_actual,
        "days_under_line": row.days_under_line,
        "projected_arc_date": row.projected_arc_date,
    }


@router.post(
    "/{slug}/commander-order",
    response={200: dict, 403: ErrorResponse},
    auth=AuthBearer(),
)
def set_commander_order(
    request, slug: str, payload: schemas.CommanderOrderRequest
):
    """The one line above today's orders, when a human writes it."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    campaign.commander_order_text = payload.text
    campaign.commander_order_set_at = timezone.now()
    campaign.commander_order_is_draft = False
    campaign.save(
        update_fields=[
            "commander_order_text",
            "commander_order_set_at",
            "commander_order_is_draft",
        ]
    )
    return {"commander_order_text": campaign.commander_order_text}


@router.post(
    "/{slug}/structures",
    response={
        200: schemas.CampaignStructureOut,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
)
def attach_structure(
    request, slug: str, payload: schemas.StructureAttachRequest
):
    """Add a structure under recon. Grows the theater to its system."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_scout(request.user, campaign):
        return _denied()

    name = payload.name
    system_name = payload.system_name
    if payload.selected_item_window.strip():
        try:
            if "Orbital Skyhook" in payload.selected_item_window:
                parsed = get_skyhook_details(payload.selected_item_window)
            else:
                parsed = get_structure_details(payload.selected_item_window)
            name = name or parsed.structure_name
            system_name = system_name or parsed.location
        except (ValueError, AttributeError) as exc:
            return 400, {"detail": f"could not parse selected item: {exc}"}

    if payload.structure_type not in STRUCTURE_TYPE_IDS:
        return 400, {
            "detail": f"unknown structure type: {payload.structure_type}"
        }

    if payload.reinforce_hour is not None and (
        payload.reinforce_hour < 0 or payload.reinforce_hour > 23
    ):
        return 400, {"detail": "reinforce_hour must be between 0 and 23"}

    timer = None
    if payload.timer_at is not None:
        valid_states = {
            choice[0] for choice in EveStructureTimer.state_choices
        }
        if not payload.timer_state or payload.timer_state not in valid_states:
            return 400, {
                "detail": "timer_state is required when timer_at is set"
            }
        timer = EveStructureTimer.objects.create(
            name=name,
            state=payload.timer_state,
            type=payload.structure_type,
            timer=payload.timer_at,
            created_by=request.user,
            corporation_name=payload.corporation_name or None,
            alliance_name=payload.alliance_name or None,
            system_name=system_name,
            fitting=payload.fitting or None,
            campaign=campaign,
        )

    try:
        if timer is not None:
            structure = structure_service.attach_timer(
                campaign,
                timer,
                created_by=request.user,
                fitting=payload.fitting,
                reinforce_hour=payload.reinforce_hour,
                corporation_id=payload.corporation_id,
                related_alliance_name=payload.related_alliance_name,
                related_alliance_id=payload.related_alliance_id,
            )
        else:
            structure = structure_service.attach_structure(
                campaign,
                name=name,
                structure_type=payload.structure_type,
                system_name=system_name,
                solar_system_id=payload.solar_system_id,
                corporation_name=payload.corporation_name,
                corporation_id=payload.corporation_id,
                alliance_name=payload.alliance_name,
                alliance_id=payload.alliance_id,
                related_alliance_name=payload.related_alliance_name,
                related_alliance_id=payload.related_alliance_id,
                created_by=request.user,
                fitting=payload.fitting,
                reinforce_hour=payload.reinforce_hour,
            )
    except ValueError as exc:
        return 400, {"detail": str(exc)}

    return serializers.structure_out(structure)


@router.post(
    "/{slug}/structures/timers",
    response={
        200: schemas.CampaignStructureOut,
        400: ErrorResponse,
        403: ErrorResponse,
        404: None,
    },
    auth=AuthBearer(),
)
def attach_structure_timer(
    request, slug: str, payload: schemas.TimerAttachRequest
):
    """Link an existing EveStructureTimer to this campaign."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()

    try:
        timer = EveStructureTimer.objects.get(id=payload.timer_id)
    except EveStructureTimer.DoesNotExist:
        return 404, None

    structure = structure_service.attach_timer(
        campaign, timer, created_by=request.user
    )
    return serializers.structure_out(structure)


@router.post(
    "/{slug}/opponents",
    response={
        200: schemas.CampaignOpponentOut,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
)
def attach_opponent(
    request, slug: str, payload: schemas.OpponentAttachRequest
):
    """Declare who this campaign is fought against."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()

    if payload.alliance_id:
        existing = campaign.opponents.filter(
            alliance_id=payload.alliance_id
        ).first()
        if existing:
            existing.name = payload.name
            existing.ticker = payload.ticker
            existing.corporation_id = payload.corporation_id
            existing.faction_id = payload.faction_id
            existing.save()
            return serializers.opponent_out(existing)

    opponent = CampaignOpponent.objects.create(
        campaign=campaign,
        name=payload.name,
        ticker=payload.ticker,
        alliance_id=payload.alliance_id,
        corporation_id=payload.corporation_id,
        faction_id=payload.faction_id,
    )
    return serializers.opponent_out(opponent)
