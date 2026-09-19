"""PATCH /{fleet_id} — update scheduled fleet (FC / privileged)."""

import logging

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import can_use_feature

from fleets.endpoints.helpers import (
    _fleet_apply_optional_scalar_updates,
    _fleet_patch_audience_location_errors,
    try_refresh_active_fleet_motd,
    update_instance_endtime,
)
from fleets.endpoints.schemas import EveFleetResponse, UpdateEveFleetRequest
from fleets.helpers.schedule_fleet import resolve_campaign
from fleets.models import EveFleet

logger = logging.getLogger(__name__)

PATH = "/{fleet_id}"
METHOD = "patch"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: EveFleetResponse,
        403: ErrorResponse,
        400: ErrorResponse,
    },
    "description": "Update the fleet details. Must have fleets.add_evefleet permission",
}


def update_fleet(request, fleet_id: int, payload: UpdateEveFleetRequest):
    if not (
        request.user.is_superuser
        or can_use_feature(request.user, "fleets.create")
    ):
        return 403, {"detail": "User missing permission fleets.add_evefleet"}

    fleet = EveFleet.objects.get(id=fleet_id)

    err = _fleet_patch_audience_location_errors(fleet, payload)
    if err:
        return 400, err
    _fleet_apply_optional_scalar_updates(fleet, payload)

    if (
        "campaign_id" in payload.model_fields_set
        and payload.campaign_id != fleet.campaign_id
    ):
        # Only a change is validated. A fleet attached to a campaign that has
        # since ended keeps it, and re-saving the fleet cannot detach it by
        # accident.
        campaign = resolve_campaign(payload.campaign_id)
        if isinstance(campaign, tuple):
            return 400, campaign[1]
        fleet.campaign = campaign

    fleet.save()

    if "doctrine_id" in payload.model_fields_set:
        try_refresh_active_fleet_motd(fleet)

    if payload.status and payload.status in ("complete", "cancelled"):
        update_instance_endtime(fleet)

    out = {
        "id": fleet.id,
        "type": fleet.type,
        "description": fleet.description,
        "objective": fleet.objective or None,
        "campaign_id": fleet.campaign_id,
        "campaign_slug": fleet.campaign.slug if fleet.campaign else None,
        "start_time": fleet.start_time,
        "fleet_commander": fleet.created_by.id if fleet.created_by else None,
        "location": (
            fleet.formup_location.location_name
            if fleet.formup_location
            else None
        ),
        "audience": fleet.audience.name if fleet.audience else None,
        "doctrine_id": fleet.doctrine.id if fleet.doctrine else None,
        "status": fleet.status,
        "disable_motd": fleet.disable_motd,
        "aar_link": fleet.aar_link,
        "roam_report_url": fleet.roam_report_url,
    }

    return EveFleetResponse(**out)
