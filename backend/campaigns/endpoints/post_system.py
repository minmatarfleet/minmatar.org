"""One endpoint: see the function below."""

from __future__ import annotations


from django.shortcuts import get_object_or_404

from app.errors import ErrorResponse
from authentication import AuthBearer

from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _can_manage, _denied
from campaigns.endpoints.settings_helpers import _system_out
from campaigns.models import (
    Campaign,
    CampaignSystem,
    SystemGoal,
    SystemPriority,
    SystemRole,
)
from feed.models import FeedMonitoredSystem


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
