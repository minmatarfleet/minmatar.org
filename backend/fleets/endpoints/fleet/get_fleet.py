"""GET /{fleet_id} — fleet detail for authorized viewers."""

from typing import Optional

from authentication import AuthBearer
from groups.helpers.feature_access import fleet_hidden_from
from tribes.helpers.publishing import host_group_ref
from tribes.schemas import RestrictedResponse, restricted

from fleets.endpoints.helpers import _fleet_authorized, fleet_host_fields

from fleets.endpoints.schemas import (
    EveFleetDetailResponse,
    EveFleetTrackingResponse,
)
from fleets.helpers.close_mail import aars_forum_url
from fleets.helpers.copy_fleet import can_copy_fleet
from fleets.helpers.private_fleet_discord import thread_url
from fleets.helpers.private_fleets import record_page_view, user_invite
from fleets.helpers.private_visibility import (
    is_hidden_private,
    private_fleet_visible_to,
)
from fleets.models import EveFleet, EveFleetInstance

PATH = "/{fleet_id}"
METHOD = "get"
ROUTE_SPEC = {
    "auth": AuthBearer(),
    "response": {
        200: EveFleetDetailResponse,
        403: Optional[RestrictedResponse],
        404: None,
    },
    "description": (
        "Get fleet by ID. Requires fleets.view_evefleet. A members-only "
        "tribe group fleet the viewer can't see is a 403 naming the group. "
        "A private fleet the viewer wasn't invited to is a 404, as if it "
        "didn't exist."
    ),
}


def get_fleet(request, fleet_id: int):
    fleet = EveFleet.objects.filter(id=fleet_id).first()
    if not fleet:
        return 404, None
    if is_hidden_private(fleet) and not private_fleet_visible_to(
        request.user, fleet
    ):
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
        "aar_forum_url": aars_forum_url(),
        "can_copy": can_copy_fleet(request.user, fleet),
        **fleet_host_fields(fleet),
        **private_fleet_fields(request.user, fleet),
    }
    if fleet.doctrine:
        payload["doctrine_id"] = fleet.doctrine.id

    return EveFleetDetailResponse(**payload)


def private_fleet_fields(user, fleet) -> dict:
    """The viewer's invite, the Invites tab and, on a private fleet, the
    thread link. Opening a private fleet's page as an invitee is recorded
    for the leak trace."""
    # pylint: disable=import-outside-toplevel
    from fleets.endpoints.private.invites import can_manage_invites

    invite = user_invite(fleet, user)
    if not fleet.invite_only:
        return {
            "my_invite_answer": invite.answer if invite else None,
            "my_invite_wave": invite.wave.number if invite else None,
            "my_invite_source": invite.source_kind if invite else None,
            "can_manage_invites": can_manage_invites(user, fleet),
        }
    if invite is not None:
        record_page_view(fleet, user)
    manages = can_manage_invites(user, fleet)
    in_thread = manages or (invite is not None and invite.answer == "in")
    return {
        "invite_only": True,
        "declassified_at": fleet.declassified_at,
        "my_invite_answer": invite.answer if invite else None,
        "my_invite_wave": invite.wave.number if invite else None,
        "my_invite_source": invite.source_kind if invite else None,
        "can_manage_invites": manages,
        "discord_thread_url": thread_url(fleet) if in_thread else None,
    }
