"""Create a scheduled EveFleet from a create payload."""

from __future__ import annotations

from django.contrib.auth.models import User

from app.errors import ErrorResponse
from fittings.models import EveDoctrine
from fleets.endpoints.helpers import fleet_host_fields, send_discord_pre_ping
from fleets.endpoints.schemas import CreateEveFleetRequest, EveFleetResponse
from fleets.helpers.fleet_location import resolve_scheduled_fleet_location
from fleets.models import EveFleet, EveFleetAudience

# A tribe group fleet's type. Strategic fleets are alliance-only and
# campaign fleets are never scheduled.
GROUP_FLEET_TYPES = ("non_strategic", "training", "npsi")


def resolve_host_group(user: User, host_group_id: int):
    """The group to host a fleet as, or a Ninja error tuple."""
    # pylint: disable=import-outside-toplevel
    from tribes.helpers.publishing import KIND_FLEET, can_publish
    from tribes.models import TribeGroup

    group = (
        TribeGroup.objects.filter(pk=host_group_id, is_active=True)
        .select_related("tribe")
        .first()
    )
    if group is None:
        return 400, ErrorResponse.new(
            f"No tribe group with id {host_group_id}"
        )
    if not can_publish(user, group, KIND_FLEET):
        return 403, ErrorResponse.new(
            f"You can't schedule fleets for {group.name}"
        )
    return group


def group_fleet_error(
    group, fleet_type: str, open_to_alliance: bool
) -> tuple[int, dict] | None:
    """A 400 for group fleet settings the group doesn't allow, or None."""
    fleet_type = getattr(fleet_type, "value", fleet_type)
    if fleet_type not in GROUP_FLEET_TYPES:
        return 400, ErrorResponse.new(
            "A group fleet must be non-strategic, training or NPSI"
        )
    if open_to_alliance and not group.allow_open_fleets:
        return 400, ErrorResponse.new(
            f"{group.name} doesn't open fleets to the alliance"
        )
    return None


def create_scheduled_fleet(
    *, user: User, payload: CreateEveFleetRequest
) -> EveFleet | tuple[int, dict]:
    if getattr(payload, "host_group_id", None):
        return create_group_fleet(user=user, payload=payload)

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
        hide_volunteers=payload.hide_volunteers,
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


def create_group_fleet(
    *, user: User, payload: CreateEveFleetRequest
) -> EveFleet | tuple[int, dict]:
    """A tribe group fleet: no audience, and never a pre-ping."""
    group = resolve_host_group(user, payload.host_group_id)
    if isinstance(group, tuple):
        return group
    error = group_fleet_error(group, payload.type, payload.open_to_alliance)
    if error:
        return error
    open_to_alliance = bool(payload.open_to_alliance)
    # Only a fleet the alliance can see goes on the #schedule message.
    on_schedule = open_to_alliance and bool(payload.on_schedule)

    location_result = resolve_scheduled_fleet_location(payload.location_id)
    if isinstance(location_result, tuple):
        return location_result

    campaign = resolve_campaign(getattr(payload, "campaign_id", None))
    if isinstance(campaign, tuple):
        return campaign

    doctrine = None
    if payload.doctrine_id:
        doctrine = EveDoctrine.objects.filter(id=payload.doctrine_id).first()

    return EveFleet.objects.create(
        type=payload.type,
        description=payload.description,
        objective=(payload.objective or "").strip(),
        start_time=payload.start_time,
        created_by=user,
        location=location_result,
        audience=None,
        host_group=group,
        open_to_alliance=open_to_alliance,
        on_schedule=on_schedule,
        doctrine=doctrine,
        disable_motd=payload.disable_motd,
        hide_volunteers=payload.hide_volunteers,
        status="pending",
        campaign=campaign,
    )


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
        "hide_volunteers": fleet.hide_volunteers,
        "status": fleet.status,
        "campaign_id": fleet.campaign_id,
        "campaign_slug": fleet.campaign.slug if fleet.campaign else None,
        **fleet_host_fields(fleet),
    }
    if fleet.doctrine:
        out["doctrine_id"] = fleet.doctrine.id
    return EveFleetResponse(**out)
