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
from groups.helpers.feature_access import require_feature

CREATE_FEATURE = "campaigns.create"
MANAGE_FEATURE = "campaigns.manage"


def _can_manage(user, campaign: Campaign) -> bool:
    if user.is_superuser or user.is_staff:
        return True
    if campaign.created_by_id == user.id:
        return True
    return require_feature(user, MANAGE_FEATURE) is None


@router.post(
    "",
    response={200: schemas.CampaignDetail, 403: ErrorResponse},
    auth=AuthBearer(),
)
def create_campaign(request, payload: schemas.CampaignCreateRequest):
    denied = require_feature(request.user, CREATE_FEATURE)
    if denied:
        return denied

    campaign = Campaign.objects.create(
        slug=payload.slug,
        short_code=payload.short_code.upper(),
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
            name=str(solar_system_id),
        )

    from campaigns.endpoints.public import get_campaign

    return get_campaign(request, campaign.slug)


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
        return 403, {"detail": "feature_denied", "feature": MANAGE_FEATURE}

    row = get_object_or_404(
        CampaignWeekTarget, id=target_id, campaign_system__campaign=campaign
    )
    row.target = payload.target
    if payload.accept:
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


@router.post("/{slug}/week/propose", response={200: dict}, auth=AuthBearer())
def propose_week(request, slug: str):
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return 403, {"detail": "feature_denied", "feature": MANAGE_FEATURE}
    proposed = plan.propose_week(campaign)
    plan.update_week_progress(campaign)
    return {"proposed": proposed}


@router.post(
    "/{slug}/commander-order", response={200: dict}, auth=AuthBearer()
)
def set_commander_order(request, slug: str, text: str):
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return 403, {"detail": "feature_denied", "feature": MANAGE_FEATURE}
    campaign.commander_order_text = text[:280]
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
