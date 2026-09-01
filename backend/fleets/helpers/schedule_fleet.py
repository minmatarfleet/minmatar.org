"""Create a scheduled EveFleet from a create payload."""

from __future__ import annotations

from django.contrib.auth.models import User

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
    }
    if fleet.doctrine:
        out["doctrine_id"] = fleet.doctrine.id
    return EveFleetResponse(**out)
