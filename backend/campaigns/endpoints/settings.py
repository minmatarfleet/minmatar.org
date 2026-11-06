"""Operator screens that used to live in Django admin.

Everything here is gated by the ``campaigns.manage`` feature (or the creator
rule in ``manage._can_manage``). The Django admin stays as break-glass.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer
from campaigns.endpoints import schemas, serializers
from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _can_manage, _denied
from campaigns.helpers import campaign_week_start
from campaigns.models import (
    Campaign,
    CampaignDailyOrder,
    CampaignFitting,
    CampaignParty,
    CampaignStatus,
    CampaignStructure,
    CampaignSystem,
    CampaignWeekTarget,
    SystemGoal,
    SystemPriority,
    SystemRole,
)
from campaigns.services import plan
from feed.models import FeedMonitoredSystem
from fittings.models import EveFitting


def _system_out(system: CampaignSystem) -> dict:
    return {
        "id": system.id,
        "solar_system_id": system.solar_system_id,
        "name": system.name,
        "goal": system.goal,
        "role": system.role,
        "priority": system.priority,
        "is_fw_objective": system.is_fw_objective,
        "retired": system.retired_at is not None,
    }


def _settings(campaign: Campaign) -> dict:
    week_start = campaign_week_start()
    return {
        "slug": campaign.slug,
        "name": campaign.name,
        "tagline": campaign.tagline,
        "description_md": campaign.description_md,
        "status": campaign.status,
        "kind": campaign.kind,
        "start_at": campaign.start_at,
        "end_at": campaign.end_at,
        "commander_order_text": campaign.commander_order_text,
        "commander_order_is_draft": campaign.commander_order_is_draft,
        "systems": [_system_out(s) for s in campaign.systems.all()],
        "areas": [serializers.area_out(a) for a in campaign.areas.all()],
        "parties": [serializers.party_out(p) for p in campaign.parties.all()],
        "structures": [
            {
                "id": structure.id,
                "name": structure.name,
                "structure_type": structure.structure_type,
                "system_name": structure.system_name,
            }
            for structure in campaign.structures.all()
        ],
        "fittings": serializers.campaign_fittings(campaign),
        "week_targets": [
            {
                "id": row.id,
                "system": row.campaign_system.name,
                "metric": row.metric,
                "target": row.target,
                "progress": row.progress,
                "proposed": row.proposed,
            }
            for row in CampaignWeekTarget.objects.filter(
                campaign_system__campaign=campaign, week_start=week_start
            ).select_related("campaign_system")
        ],
        "daily_orders": [
            {
                "id": order.id,
                "kind": order.kind,
                "points": order.points,
                "system": (
                    order.campaign_system.name if order.campaign_system else ""
                ),
            }
            for order in CampaignDailyOrder.objects.filter(
                campaign=campaign, day=timezone.localdate()
            ).select_related("campaign_system")
        ],
    }


@router.get(
    "/{slug}/settings",
    response={200: schemas.CampaignSettingsOut, 403: ErrorResponse},
    auth=AuthBearer(),
)
def get_settings(request, slug: str):
    """Everything an operator edits on one campaign, in one read."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    return _settings(campaign)


# Not "/{slug}": ninja pins a path's position at its first registration, and
# that pattern has to stay behind /entities and /overlay in public.py.
@router.patch(
    "/{slug}/settings",
    response={
        200: schemas.CampaignSettingsOut,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
)
def patch_campaign(request, slug: str, payload: schemas.CampaignPatchRequest):
    """Rename, reschedule, or move a campaign between draft and live."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()

    if payload.status is not None and payload.status not in (
        CampaignStatus.values
    ):
        return 400, {"detail": f"unknown status: {payload.status}"}
    start_at = payload.start_at or campaign.start_at
    end_at = payload.end_at or campaign.end_at
    if end_at <= start_at:
        return 400, {"detail": "end_at must be after start_at"}

    fields = []
    for name in ("name", "tagline", "description_md", "status"):
        value = getattr(payload, name)
        if value is not None:
            setattr(campaign, name, value)
            fields.append(name)
    campaign.start_at = start_at
    campaign.end_at = end_at
    campaign.save(update_fields=fields + ["start_at", "end_at"])
    return _settings(campaign)


@router.post(
    "/{slug}/systems",
    response={
        200: schemas.SettingsSystemOut,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
)
def add_system(request, slug: str, payload: schemas.SystemAddRequest):
    """Add a monitored system to the campaign, or bring a retired one back."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()

    monitored = FeedMonitoredSystem.objects.filter(
        solar_system_id=payload.solar_system_id
    ).first()
    if not monitored:
        return 400, {
            "detail": f"unknown solar system id: {payload.solar_system_id}"
        }
    for value, choices, label in (
        (payload.goal, SystemGoal.values, "goal"),
        (payload.role, SystemRole.values, "role"),
        (payload.priority, SystemPriority.values, "priority"),
    ):
        if value is not None and value not in choices:
            return 400, {"detail": f"unknown {label}: {value}"}

    defaults = {"name": monitored.name, "retired_at": None}
    if payload.goal:
        defaults["goal"] = payload.goal
    if payload.role:
        defaults["role"] = payload.role
    if payload.priority:
        defaults["priority"] = payload.priority
    system, _ = CampaignSystem.objects.update_or_create(
        campaign=campaign,
        solar_system_id=payload.solar_system_id,
        defaults=defaults,
    )
    return _system_out(system)


@router.delete(
    "/{slug}/systems/{system_id}",
    response={200: dict, 403: ErrorResponse},
    auth=AuthBearer(),
)
def retire_system(request, slug: str, system_id: int):
    """Retire, not delete: the history of kills and targets stays attached."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    system = get_object_or_404(CampaignSystem, id=system_id, campaign=campaign)
    system.retired_at = timezone.now()
    system.save(update_fields=["retired_at"])
    return {"retired": True}


@router.delete(
    "/{slug}/parties/{party_id}",
    response={200: dict, 403: ErrorResponse},
    auth=AuthBearer(),
)
def delete_party(request, slug: str, party_id: int):
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    get_object_or_404(CampaignParty, id=party_id, campaign=campaign).delete()
    return {"deleted": True}


@router.delete(
    "/{slug}/structures/{structure_id}",
    response={200: dict, 403: ErrorResponse},
    auth=AuthBearer(),
)
def delete_structure(request, slug: str, structure_id: int):
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    get_object_or_404(
        CampaignStructure, id=structure_id, campaign=campaign
    ).delete()
    return {"deleted": True}


@router.post(
    "/{slug}/fittings",
    response={
        200: schemas.CampaignFittingOut,
        400: ErrorResponse,
        403: ErrorResponse,
    },
    auth=AuthBearer(),
)
def add_fitting(request, slug: str, payload: schemas.FittingAddRequest):
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    fitting = EveFitting.objects.filter(id=payload.fitting_id).first()
    if not fitting:
        return 400, {"detail": f"unknown fitting id: {payload.fitting_id}"}
    row, _ = CampaignFitting.objects.update_or_create(
        campaign=campaign,
        fitting=fitting,
        defaults={
            "role_label": payload.role_label,
            "srp_eligible": payload.srp_eligible,
        },
    )
    return serializers.fitting_out(row)


@router.delete(
    "/{slug}/fittings/{row_id}",
    response={200: dict, 403: ErrorResponse},
    auth=AuthBearer(),
)
def delete_fitting(request, slug: str, row_id: int):
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    get_object_or_404(CampaignFitting, id=row_id, campaign=campaign).delete()
    return {"deleted": True}


@router.post(
    "/{slug}/commander-order/draft",
    response={200: dict, 403: ErrorResponse},
    auth=AuthBearer(),
)
def draft_commander_order(request, slug: str):
    """Write the order from the week plan and keep it as a draft."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    campaign.commander_order_text = plan.draft_commander_order(campaign)
    campaign.commander_order_set_at = timezone.now()
    campaign.commander_order_is_draft = True
    campaign.save(
        update_fields=[
            "commander_order_text",
            "commander_order_set_at",
            "commander_order_is_draft",
        ]
    )
    return {
        "commander_order_text": campaign.commander_order_text,
        "commander_order_is_draft": True,
    }


@router.post(
    "/{slug}/commander-order/publish",
    response={200: dict, 400: ErrorResponse, 403: ErrorResponse},
    auth=AuthBearer(),
)
def publish_commander_order(request, slug: str):
    """Clear the draft flag so pilots see the order."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    if not campaign.commander_order_text.strip():
        return 400, {"detail": "the order is empty"}
    campaign.commander_order_is_draft = False
    campaign.commander_order_set_at = timezone.now()
    campaign.save(
        update_fields=["commander_order_is_draft", "commander_order_set_at"]
    )
    return {
        "commander_order_text": campaign.commander_order_text,
        "commander_order_is_draft": False,
    }
