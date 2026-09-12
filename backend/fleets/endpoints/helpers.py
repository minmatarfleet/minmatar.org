"""Shared helpers for fleet HTTP endpoints."""

import logging
from datetime import datetime
from typing import Optional

from django.utils import timezone

from discord.client import DiscordClient
from fittings.models import EveDoctrine
from groups.helpers.feature_access import can_use_feature

from fleets.models import (
    EveFleet,
    EveFleetAudience,
    EveFleetInstance,
    close_fleet_cleanup,
)
from fleets.helpers.fleet_location import resolve_scheduled_fleet_location
from fleets.helpers.roam_report import schedule_roam_report
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
        "audience": fleet.audience.name if fleet.audience else None,
        "tracking": tracking,
        "disable_motd": fleet.disable_motd,
        "status": fixup_fleet_status(fleet, tracking),
        "doctrine_id": fleet.doctrine.id if fleet.doctrine else None,
        "aar_link": fleet.aar_link,
        "roam_report_url": fleet.roam_report_url,
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
    if can_use_feature(request.user, "fleets.view", fleet=fleet):
        return True
    if request.user == fleet.created_by:
        return True
    return False


def send_discord_pre_ping(fleet: EveFleet) -> bool:
    """Send a Discord pre-ping for a fleet."""
    if not fleet.audience:
        return False

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
        location_result = resolve_scheduled_fleet_location(payload.location_id)
        if isinstance(location_result, tuple):
            _, body = location_result
            return body
        fleet.location = location_result
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
    # An explicit null clears the doctrine ("No doctrine" in the edit form).
    if "doctrine_id" in payload.model_fields_set:
        fleet.doctrine = (
            EveDoctrine.objects.get(id=payload.doctrine_id)
            if payload.doctrine_id
            else None
        )
    if payload.aar_link:
        fleet.aar_link = payload.aar_link


def update_instance_endtime(fleet: EveFleet) -> None:
    closed_tracking = False
    for instance in EveFleetInstance.objects.filter(eve_fleet=fleet):
        if not instance.end_time:
            instance.end_time = timezone.now()
            instance.save()
            closed_tracking = True
    close_fleet_cleanup(fleet)
    if closed_tracking and fleet.status == "complete":
        schedule_roam_report(fleet.id)


def try_refresh_active_fleet_motd(fleet: EveFleet) -> None:
    """Regenerate and push MOTD when the fleet is actively tracked."""
    if fleet.disable_motd:
        return
    instance = EveFleetInstance.objects.filter(
        eve_fleet=fleet, end_time__isnull=True
    ).first()
    if not instance:
        return
    try:
        instance.refresh_motd()
    except Exception as e:
        logger.warning("Failed to refresh MOTD for fleet %s: %s", fleet.id, e)


def _fleet_manager(request, fleet: EveFleet) -> bool:
    """True if user may manage FC-only fleet settings (refits, cyno systems)."""
    if request.user == fleet.created_by:
        return True
    return can_use_feature(request.user, "fleets.delete")


def make_role_volunteer_response(volunteer, reveal_system: bool = False):
    """
    Serialize a role volunteer. The assigned cyno system is private: it is
    only included when ``reveal_system`` is True (FC or the pilot's own user).
    """
    from fleets.endpoints.schemas import (  # pylint: disable=import-outside-toplevel
        EveFleetRoleVolunteerResponse,
    )

    return EveFleetRoleVolunteerResponse(
        id=volunteer.id,
        character_id=volunteer.character_id,
        character_name=volunteer.character_name,
        role=volunteer.role,
        subtype=volunteer.subtype,
        quantity=volunteer.quantity,
        solar_system_id=volunteer.solar_system_id if reveal_system else None,
        solar_system_name=(
            (volunteer.solar_system_name or None) if reveal_system else None
        ),
    )


def _system_reveal_predicate(request, fleet: EveFleet):
    """Return volunteer -> bool: may this requester see its cyno system?"""
    from eveonline.helpers.characters import (  # pylint: disable=import-outside-toplevel
        user_characters,
    )

    if _fleet_manager(request, fleet):
        return lambda volunteer: True
    own_ids = {c.character_id for c in user_characters(request.user)}
    return lambda volunteer: volunteer.character_id in own_ids


def make_ship_volunteer_response(volunteer):
    from fleets.endpoints.schemas import (  # pylint: disable=import-outside-toplevel
        EveFleetShipVolunteerResponse,
    )

    return EveFleetShipVolunteerResponse(
        id=volunteer.id,
        character_id=volunteer.character_id,
        character_name=volunteer.character_name,
        fitting_id=volunteer.fitting_id,
        fleet_fitting_id=volunteer.fleet_fitting_id,
        fitting_name=volunteer.target_name,
        ship_id=volunteer.target_ship_id,
    )


def make_composition_entry_response(entry):
    from fleets.endpoints.schemas import (  # pylint: disable=import-outside-toplevel
        EveFleetCompositionEntryResponse,
        EveFleetFittingRefitOption,
    )

    return EveFleetCompositionEntryResponse(
        key=entry.key,
        fitting_id=entry.fitting_id,
        fleet_fitting_id=entry.fleet_fitting_id,
        name=entry.name,
        ship_id=entry.ship_id,
        ship_name=entry.ship_name,
        ship_group=entry.ship_group,
        role=entry.role,
        source=entry.source,
        eft_format=entry.eft_format,
        refits=[
            EveFleetFittingRefitOption(id=rid, name=rname)
            for rid, rname in entry.refits
        ],
        module_slots=entry.module_slots,
    )


def make_fleet_refit_response(refit):
    from fleets.endpoints.schemas import (  # pylint: disable=import-outside-toplevel
        EveFleetFittingRefitModule,
        EveFleetFittingRefitResponse,
    )
    from fleets.helpers.refits import (  # pylint: disable=import-outside-toplevel
        parse_cargo_modules,
        resolve_module_type_ids,
    )

    modules = parse_cargo_modules(refit.cargo_modules)
    type_ids = resolve_module_type_ids([name for name, _ in modules])
    return EveFleetFittingRefitResponse(
        id=refit.id,
        fitting_id=refit.fitting_id,
        fleet_fitting_id=refit.fleet_fitting_id,
        fitting_name=refit.target_name,
        ship_id=refit.target_ship_id,
        refit_id=refit.refit_id,
        name=refit.name,
        cargo_modules=refit.cargo_modules,
        eft_format=refit.eft_format,
        esi_fitting_id=refit.esi_fitting_id,
        modules=[
            EveFleetFittingRefitModule(
                name=name, quantity=qty, type_id=type_ids.get(name)
            )
            for name, qty in modules
        ],
        notes=refit.notes,
    )
