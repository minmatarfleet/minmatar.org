"""Operator endpoints. A campaign runs with a name, systems and dates."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.endpoints.base import router
from campaigns.endpoints import schemas
from campaigns.models import (
    Campaign,
    CampaignStatus,
    CampaignSystem,
    CampaignWeekTarget,
)
from campaigns.services import plan
from feed.models import FeedMonitoredSystem
from groups.helpers.feature_access import require_feature

CREATE_FEATURE = "campaigns.create"
MANAGE_FEATURE = "campaigns.manage"


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


def _denied():
    return 403, {"detail": "feature_denied", "feature": MANAGE_FEATURE}


@router.post(
    "",
    response={200: schemas.CampaignDetail, 403: ErrorResponse},
    auth=AuthBearer(),
)
def create_campaign(request, payload: schemas.CampaignCreateRequest):
    """Create a draft. Systems are named from the feed's monitored list."""
    denied = require_feature(request.user, CREATE_FEATURE)
    if denied:
        return denied

    if payload.end_at <= payload.start_at:
        return 400, {"detail": "end_at must be after start_at"}

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
        )

    return {
        "slug": campaign.slug,
        "short_code": campaign.short_code,
        "name": campaign.name,
        "status": campaign.status,
        "systems": [system.name for system in campaign.systems.all()],
    }


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
