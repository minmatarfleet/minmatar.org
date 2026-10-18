"""PATCH /{fleet_id} — update scheduled fleet (FC / privileged)."""

import logging

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import can_use_feature
from tribes.helpers.permissions import user_can_manage_group

from fleets.endpoints.helpers import (
    _fleet_apply_optional_scalar_updates,
    _fleet_manager,
    _fleet_patch_audience_location_errors,
    fleet_host_fields,
    is_strategic_fc,
    try_refresh_active_fleet_motd,
    update_instance_endtime,
)
from fleets.endpoints.schemas import EveFleetResponse, UpdateEveFleetRequest
from fleets.helpers.schedule_fleet import (
    group_fleet_error,
    resolve_campaign,
    resolve_host_group,
)
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
    "description": (
        "Update the fleet details. Must be the fleet's FC or a Strategic FC "
        "(a tribe group fleet: or a manager of the group)."
    ),
}


def _can_manage_group_fleet(request, fleet: EveFleet) -> bool:
    """A group fleet's FC, a Strategic FC or a manager of its group."""
    if _fleet_manager(request, fleet):
        return True
    return user_can_manage_group(request.user, fleet.host_group)


def _apply_host_group(request, fleet: EveFleet, payload):
    """Move the fleet into or out of a tribe group; None or an error."""
    if "host_group_id" not in payload.model_fields_set:
        return None
    if payload.host_group_id == fleet.host_group_id:
        return None
    if payload.host_group_id:
        group = resolve_host_group(request.user, payload.host_group_id)
        if isinstance(group, tuple):
            return group
        fleet.host_group = group
        fleet.audience = None
        return None
    # Back to an alliance fleet: needs an audience and fleets.create.
    if not can_use_feature(request.user, "fleets.create"):
        return 403, {"detail": "User missing permission fleets.add_evefleet"}
    if not payload.audience_id:
        return 400, {"detail": "An alliance fleet needs an audience"}
    fleet.host_group = None
    fleet.open_to_alliance = False
    fleet.on_schedule = False
    return None


def _apply_group_flags(fleet: EveFleet, payload):
    """Validate and apply a group fleet's type and open/schedule flags."""
    if not fleet.host_group_id:
        return None
    if "open_to_alliance" in payload.model_fields_set:
        fleet.open_to_alliance = bool(payload.open_to_alliance)
    if "on_schedule" in payload.model_fields_set:
        fleet.on_schedule = bool(payload.on_schedule)
    opening = (
        "open_to_alliance" in payload.model_fields_set
        and fleet.open_to_alliance
    )
    error = group_fleet_error(fleet.host_group, fleet.type, opening)
    if error:
        return error
    fleet.audience = None
    fleet.on_schedule = fleet.open_to_alliance and fleet.on_schedule
    return None


def update_fleet(request, fleet_id: int, payload: UpdateEveFleetRequest):
    fleet = EveFleet.objects.get(id=fleet_id)
    moving_into_group = bool(payload.host_group_id) and (
        "host_group_id" in payload.model_fields_set
    )
    if fleet.host_group_id:
        # Group fleets: their FC or the group's managers. Creating alliance
        # fleets is not needed.
        if not _can_manage_group_fleet(request, fleet):
            return 403, {"detail": "Only this fleet's FC may update it"}
    else:
        if not (
            request.user.is_superuser
            or can_use_feature(request.user, "fleets.create")
            or is_strategic_fc(request.user)
            or moving_into_group
        ):
            return 403, {
                "detail": "User missing permission fleets.add_evefleet"
            }
        # Same rule as the website's manage menu: the fleet's own FC, or a
        # Strategic FC. Being able to create fleets is not enough.
        if not _fleet_manager(request, fleet):
            return 403, {"detail": "Only this fleet's FC may update it"}

    error = _apply_host_group(request, fleet, payload)
    if error:
        return error

    if fleet.host_group_id and payload.audience_id:
        # A group fleet has no audience; the id is ignored.
        payload = payload.model_copy(update={"audience_id": None})
    err = _fleet_patch_audience_location_errors(fleet, payload)
    if err:
        return 400, err
    _fleet_apply_optional_scalar_updates(fleet, payload)

    error = _apply_group_flags(fleet, payload)
    if error:
        return error

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

    if (
        "doctrine_id" in payload.model_fields_set
        or "hide_volunteers" in payload.model_fields_set
    ):
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
        "hide_volunteers": fleet.hide_volunteers,
        "aar_link": fleet.aar_link,
        "roam_report_url": fleet.roam_report_url,
        **fleet_host_fields(fleet),
    }

    return EveFleetResponse(**out)
