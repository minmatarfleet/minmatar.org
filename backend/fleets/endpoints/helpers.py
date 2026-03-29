"""Shared helpers for fleet HTTP endpoints."""

import logging
from datetime import datetime
from typing import Optional

from django.utils import timezone

from discord.client import DiscordClient
from eveonline.models import EveLocation
from fittings.models import EveDoctrine

from fleets.models import EveFleet, EveFleetAudience, EveFleetInstance
from fleets.endpoints.schemas import EveFleetResponse, EveFleetTrackingResponse
from fleets.notifications import get_fleet_discord_notification

logger = logging.getLogger(__name__)


def fixup_fleet_status(
    fleet: EveFleet, tracking: Optional[EveFleetTrackingResponse]
) -> str:
    """Override status for older fleets."""
    if not fleet:
        return None
    if not fleet.status:
        return None

    if fleet.status == "active" and tracking:
        if tracking.end_time:
            return "complete"

    return fleet.status


def make_fleet_response(fleet: EveFleet) -> EveFleetResponse:
    tracking = None
    if EveFleetInstance.objects.filter(eve_fleet=fleet).exists():
        tracking = EveFleetTrackingResponse.model_validate(
            EveFleetInstance.objects.get(eve_fleet=fleet)
        )

    return {
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
        "audience": fleet.audience.name,
        "tracking": tracking,
        "disable_motd": fleet.disable_motd,
        "status": fixup_fleet_status(fleet, tracking),
    }


def time_region(time: datetime) -> str:
    match time.hour:
        case 22 | 23 | 0 | 1 | 2 | 3 | 4:
            return "US"
        case 5 | 6 | 7 | 8 | 9:
            return "US_AP"
        case 10 | 11 | 12 | 13 | 14:
            return "AP"
        case 15 | 16 | 17 | 18 | 19:
            return "EU"
        case 20 | 21:
            return "EU_US"
        case _:
            return "??"


def _fleet_authorized(request, fleet: EveFleet) -> bool:
    """True if user can view this fleet (and thus list/volunteer for roles)."""
    if request.user.has_perm("fleets.view_evefleet"):
        return True
    if request.user == fleet.created_by:
        return True
    for group in fleet.audience.groups.all():
        if group in request.user.groups.all():
            return True
    return False


def send_discord_pre_ping(fleet: EveFleet) -> bool:
    """Send a Discord pre-ping for a fleet."""
    notification = get_fleet_discord_notification(
        is_pre_ping=True,
        fleet_id=fleet.id,
        fleet_type=fleet.get_type_display(),
        fleet_location=(
            fleet.formup_location.location_name
            if fleet.formup_location
            else "Ask FC"
        ),
        fleet_audience=fleet.audience.name,
        fleet_commander_name=fleet.fleet_commander.character_name,
        fleet_commander_id=fleet.fleet_commander.character_id,
        fleet_description=fleet.description,
        fleet_voice_channel=None,
        fleet_voice_channel_link=None,
        fleet_start_time=fleet.start_time,
    )

    try:
        DiscordClient().create_message(
            channel_id=fleet.audience.discord_channel_id,
            payload=notification,
        )
        return True
    except Exception as e:
        logger.error(
            "Error sending Discord pre-ping for fleet %d : %s",
            fleet.id,
            str(e),
        )
        return False


def _fleet_patch_audience_location_errors(
    fleet: EveFleet, payload
) -> Optional[dict]:
    if payload.audience_id:
        if not EveFleetAudience.objects.filter(
            id=payload.audience_id
        ).exists():
            return {"detail": "Audience does not exist"}
        fleet.audience = EveFleetAudience.objects.get(id=payload.audience_id)

    if payload.location_id:
        if not EveLocation.objects.filter(
            location_id=payload.location_id
        ).exists():
            return {"detail": "Location does not exist"}
        fleet.location = EveLocation.objects.get(
            location_id=payload.location_id
        )
    return None


def _fleet_apply_optional_scalar_updates(fleet: EveFleet, payload) -> None:
    if payload.type:
        fleet.type = payload.type
    if payload.description:
        fleet.description = payload.description
    if "objective" in payload.model_fields_set:
        fleet.objective = (payload.objective or "").strip()
    if payload.start_time:
        fleet.start_time = payload.start_time
    if payload.status:
        fleet.status = payload.status
    if payload.doctrine_id:
        fleet.doctrine = EveDoctrine.objects.get(id=payload.doctrine_id)
    if payload.aar_link:
        fleet.aar_link = payload.aar_link


def update_instance_endtime(fleet: EveFleet) -> None:
    for instance in EveFleetInstance.objects.filter(eve_fleet=fleet):
        if not instance.end_time:
            instance.end_time = timezone.now()
            instance.save()
