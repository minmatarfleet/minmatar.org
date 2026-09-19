"""Create a scheduled EveFleet from a create payload."""

from __future__ import annotations

from django.contrib.auth.models import User

from app.errors import ErrorResponse
from fittings.models import EveDoctrine
from fleets.endpoints.helpers import send_discord_pre_ping
from fleets.endpoints.schemas import CreateEveFleetRequest, EveFleetResponse
from fleets.helpers.fleet_location import resolve_scheduled_fleet_location
from fleets.models import EveFleet, EveFleetAudience


def create_scheduled_fleet(
    *, user: User, payload: CreateEveFleetRequest
) -> EveFleet | tuple[int, dict]:
    if not EveFleetAudience.objects.filter(id=payload.audience_id).exists():
        return 400, {"detail": "Audience does not exist"}

    audience = EveFleetAudience.objects.get(id=payload.audience_id)

    location_result = resolve_scheduled_fleet_location(payload.location_id)
    if isinstance(location_result, tuple):
        return location_result
    location = location_result

    campaign = resolve_campaign(getattr(payload, "campaign_id", None))
    if isinstance(campaign, tuple):
        return campaign

    fleet = EveFleet.objects.create(
        type=payload.type,
        description=payload.description,
        objective=(payload.objective or "").strip(),
        start_time=payload.start_time,
        created_by=user,
        location=location,
        audience=audience,
        disable_motd=payload.disable_motd,
        status="pending",
        campaign=campaign,
    )

    if payload.doctrine_id:
        doctrine = EveDoctrine.objects.get(id=payload.doctrine_id)
        fleet.doctrine = doctrine
        fleet.save()

    immediate_ping = payload.immediate_ping
    if not fleet.audience.add_to_schedule:
        immediate_ping = True

    if immediate_ping:
        send_discord_pre_ping(fleet)

    return fleet


def resolve_campaign(campaign_id):
    """A fleet can count towards a campaign that is running or about to.

    Returns the campaign, None when no campaign was asked for, or a Ninja
    error tuple.
    """
    if not campaign_id:
        return None

    # Imported here on purpose: campaigns depends on fleets, so importing it
    # at module level would close the loop.
    from campaigns.models import (  # pylint: disable=import-outside-toplevel
        Campaign,
        CampaignStatus,
    )

    # A bad id in the body is a bad request, not a missing page.
    campaign = Campaign.objects.filter(id=campaign_id).first()
    if not campaign:
        return 400, ErrorResponse.new(f"No campaign with id {campaign_id}")
    if campaign.status not in (
        CampaignStatus.SCHEDULED,
        CampaignStatus.ACTIVE,
    ):
        return 400, ErrorResponse.new(
            f"Campaign {campaign.slug} is {campaign.status}"
        )
    return campaign


def fleet_create_response(fleet: EveFleet) -> EveFleetResponse:
    out = {
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
        "disable_motd": fleet.disable_motd,
        "status": fleet.status,
        "campaign_id": fleet.campaign_id,
        "campaign_slug": fleet.campaign.slug if fleet.campaign else None,
    }
    if fleet.doctrine:
        out["doctrine_id"] = fleet.doctrine.id
    return EveFleetResponse(**out)
