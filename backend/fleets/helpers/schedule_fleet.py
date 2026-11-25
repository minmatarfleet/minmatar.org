"""Create a scheduled EveFleet from a create payload."""

from __future__ import annotations

from django.contrib.auth.models import User

from app.errors import ErrorResponse
from fittings.models import EveDoctrine
from fleets.helpers.voice_options import (
    fleet_voice_fields,
    resolve_fleet_voice,
)
from fleets.endpoints.helpers import fleet_host_fields, send_discord_pre_ping
from fleets.endpoints.schemas import CreateEveFleetRequest, EveFleetResponse
from fleets.helpers.fleet_doctrine import doctrine_choice_error
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


def group_fleet_track_mining(group, payload) -> bool:
    """The request's track_mining, or the group's default when left out."""
    requested = getattr(payload, "track_mining", None)
    if requested is None:
        return bool(group.track_mining_by_default)
    return bool(requested)


def create_scheduled_fleet(
    *, user: User, payload: CreateEveFleetRequest
) -> EveFleet | tuple[int, dict]:
    invite_only = bool(getattr(payload, "invite_only", False))
    if invite_only:
        error = private_fleet_error(user, payload)
        if error:
            return error
    error = doctrine_choice_error(payload.doctrine_id)
    if error:
        return error
    if getattr(payload, "host_group_id", None):
        return create_group_fleet(user=user, payload=payload)

    if not EveFleetAudience.objects.filter(id=payload.audience_id).exists():
        return 400, {"detail": "Audience does not exist"}

    audience = EveFleetAudience.objects.get(id=payload.audience_id)

    location_result = resolve_scheduled_fleet_location(payload.location_id)
    if isinstance(location_result, tuple):
        return location_result
    location = location_result

    campaign = resolve_campaign(
        getattr(payload, "campaign_id", None), user, invite_only
    )
    if isinstance(campaign, tuple):
        return campaign
    voice = resolve_fleet_voice(payload)
    if isinstance(voice, tuple):
        return voice

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
        track_mining=bool(getattr(payload, "track_mining", None)),
        status="pending",
        campaign=campaign,
        invite_only=invite_only,
        **voice,
    )

    if payload.doctrine_id:
        doctrine = EveDoctrine.objects.get(id=payload.doctrine_id)
        fleet.doctrine = doctrine
        fleet.save()

    immediate_ping = payload.immediate_ping
    if not fleet.audience.add_to_schedule:
        immediate_ping = True

    # A private fleet never pings its audience before it starts.
    if immediate_ping and not invite_only:
        send_discord_pre_ping(fleet)

    return fleet


def create_group_fleet(
    *, user: User, payload: CreateEveFleetRequest
) -> EveFleet | tuple[int, dict]:
    """A tribe group fleet: no audience. ``immediate_ping`` sends the quiet
    group pre-ping (``send_discord_pre_ping``)."""
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

    campaign = resolve_campaign(getattr(payload, "campaign_id", None), user)
    if isinstance(campaign, tuple):
        return campaign
    voice = resolve_fleet_voice(payload)
    if isinstance(voice, tuple):
        return voice

    doctrine = None
    if payload.doctrine_id:
        doctrine = EveDoctrine.objects.filter(id=payload.doctrine_id).first()

    fleet = EveFleet.objects.create(
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
        track_mining=group_fleet_track_mining(group, payload),
        status="pending",
        campaign=campaign,
        **voice,
    )
    if payload.immediate_ping:
        send_discord_pre_ping(fleet)
    return fleet


def private_fleet_error(user: User, payload) -> tuple[int, dict] | None:
    """A private fleet is an alliance fleet a Strategic FC creates. Its
    campaign, if any, must be undisclosed (``resolve_campaign``)."""
    # pylint: disable=import-outside-toplevel
    from fleets.endpoints.helpers import is_strategic_fc

    if not (user.is_superuser or is_strategic_fc(user)):
        return 403, ErrorResponse.new(
            "Only Strategic FCs can create private fleets"
        )
    if getattr(payload, "host_group_id", None):
        return 400, ErrorResponse.new(
            "A tribe group fleet can't be invite only"
        )
    return None


def resolve_campaign(campaign_id, user=None, invite_only: bool = False):
    """A fleet can count towards a campaign that is running or about to.

    An undisclosed campaign takes fleets only from people who may see it
    (managers, coordinators, role holders); to anyone else it does not
    exist. A private fleet can count only towards an undisclosed campaign:
    a public campaign page would list it.

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
        CampaignStatus.PAUSED,
    ):
        return 400, ErrorResponse.new(
            f"Campaign {campaign.slug} is {campaign.status}"
        )
    if campaign.undisclosed and user is not None:
        # pylint: disable-next=import-outside-toplevel
        from campaigns.services.disclosure import sees_details

        if not sees_details(user, campaign):
            return 400, ErrorResponse.new(f"No campaign with id {campaign_id}")
    if invite_only and not campaign.undisclosed:
        return 400, ErrorResponse.new(
            "A private fleet can only count towards an undisclosed campaign"
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
        "track_mining": fleet.track_mining,
        "status": fleet.status,
        "campaign_id": fleet.campaign_id,
        "campaign_slug": fleet.campaign.slug if fleet.campaign else None,
        **fleet_host_fields(fleet),
        **fleet_voice_fields(fleet),
    }
    if fleet.doctrine:
        out["doctrine_id"] = fleet.doctrine.id
    return EveFleetResponse(**out)
