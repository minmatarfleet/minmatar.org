"""GET /{fleet_id} — fleet detail for authorized viewers."""

from typing import Optional

from authentication import AuthBearer
from groups.helpers.feature_access import fleet_hidden_from
from tribes.helpers.publishing import host_group_ref
from tribes.schemas import RestrictedResponse, restricted

from fleets.endpoints.helpers import _fleet_authorized, fleet_host_fields

from fleets.endpoints.schemas import EveFleetResponse, EveFleetTrackingResponse
from fleets.models import EveFleet, EveFleetInstance

PATH = "/{fleet_id}"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: EveFleetResponse,
        403: Optional[RestrictedResponse],
        404: None,
    },
    "description": (
        "Get fleet by ID. Requires fleets.view_evefleet. A members-only "
        "tribe group fleet the viewer can't see is a 403 naming the group."
    ),
}


def get_fleet(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if not _fleet_authorized(request, fleet):
        if fleet_hidden_from(request.user, fleet):
            return restricted(host_group_ref(fleet.host_group))
        return 403, None

    tracking = None
    if EveFleetInstance.objects.filter(eve_fleet=fleet).exists():
        tracking = EveFleetTrackingResponse.model_validate(
            EveFleetInstance.objects.get(eve_fleet=fleet)
        )

    payload = {
        "id": fleet.id,
        "type": fleet.type,
        "description": fleet.description,
        "objective": fleet.objective or None,
        "start_time": fleet.start_time,
        "fleet_commander": fleet.created_by.id if fleet.created_by else 0,
        "location": (
            fleet.formup_location.location_name
            if fleet.formup_location
            else "Ask FC"
        ),
        "audience": fleet.audience.name if fleet.audience else None,
        "tracking": tracking,
        "disable_motd": fleet.disable_motd,
        "hide_volunteers": fleet.hide_volunteers,
        "status": fleet.status,
        "aar_link": fleet.aar_link,
        "campaign_id": fleet.campaign_id,
        "campaign_slug": fleet.campaign.slug if fleet.campaign else None,
        "roam_report_url": fleet.roam_report_url,
        **fleet_host_fields(fleet),
    }
    if fleet.doctrine:
        payload["doctrine_id"] = fleet.doctrine.id

    return EveFleetResponse(**payload)
