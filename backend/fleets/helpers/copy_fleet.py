"""Copy a fleet to a new date: the FC's settings and ships, no sign-ups.

The copy is scheduled exactly like a fleet from the form (same permission
checks, same #schedule refresh and audience ping), so the only new rule is
which settings carry over. A setting that can no longer be used on the new
date is left off and named in ``not_copied`` instead of failing the copy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from app.errors import ErrorResponse
from groups.helpers.feature_access import can_use_feature
from tribes.helpers.permissions import user_can_manage_group

from fleets.endpoints.helpers import is_strategic_fc
from fleets.endpoints.schemas import CreateEveFleetRequest
from fleets.helpers.schedule_fleet import create_scheduled_fleet
from fleets.models import (
    CAMPAIGN_FLEET_TYPES,
    EveFleet,
    EveFleetFitting,
    EveFleetFittingRefit,
    EveFleetShipTarget,
)

# Keys of ``not_copied``: the website names each one.
NOT_COPIED_CAMPAIGN = "campaign"
NOT_COPIED_LOCATION = "location"
NOT_COPIED_OPEN_TO_ALLIANCE = "open_to_alliance"


@dataclass
class FleetCopy:
    fleet: EveFleet
    not_copied: list[str] = field(default_factory=list)


def _manages(user: User, fleet: EveFleet) -> bool:
    """The fleet's FC, a Strategic FC, a fleet admin or the group's managers."""
    if user == fleet.created_by:
        return True
    if is_strategic_fc(user) or can_use_feature(user, "fleets.delete"):
        return True
    return bool(fleet.host_group_id) and user_can_manage_group(
        user, fleet.host_group
    )


def can_schedule_for_host(user: User, fleet: EveFleet) -> bool:
    """May the user schedule a fleet for this fleet's host today?"""
    if fleet.host_group_id:
        # pylint: disable=import-outside-toplevel
        from tribes.helpers.publishing import KIND_FLEET, can_publish

        return can_publish(user, fleet.host_group, KIND_FLEET)
    return can_use_feature(user, "fleets.create")


def can_copy_fleet(user: User, fleet: EveFleet) -> bool:
    """Who sees Copy this fleet: someone who manages it and may schedule it."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if fleet.type in CAMPAIGN_FLEET_TYPES:
        return False
    return _manages(user, fleet) and can_schedule_for_host(user, fleet)


def copy_denied(user: User, fleet: EveFleet) -> tuple[int, dict] | None:
    """The 400/403 for a copy this user may not make, or None."""
    if fleet.type in CAMPAIGN_FLEET_TYPES:
        return 400, ErrorResponse.new(
            "Campaign standing fleets and gangs are never scheduled, so they "
            "can't be copied"
        )
    if not _manages(user, fleet):
        return 403, ErrorResponse.new("Only this fleet's FC may copy it")
    if not fleet.host_group_id and not can_use_feature(user, "fleets.create"):
        return 403, ErrorResponse.new(
            "User missing permission fleets.add_evefleet"
        )
    # A group fleet's publishing right is checked when the copy is made,
    # with the same message the form gets.
    return None


def _campaign_for(fleet: EveFleet, start_time: datetime):
    """The campaign the copy can count towards, or None."""
    campaign = fleet.campaign
    if campaign is None:
        return None
    # pylint: disable=import-outside-toplevel
    from campaigns.models import CampaignStatus

    if campaign.status not in (
        CampaignStatus.SCHEDULED,
        CampaignStatus.ACTIVE,
    ):
        return None
    if campaign.end_at and campaign.end_at <= start_time:
        return None
    return campaign


def _copy_request(
    fleet: EveFleet, start_time: datetime, not_copied: list[str]
) -> CreateEveFleetRequest:
    """The create payload: the old fleet's settings on the new date."""
    campaign = _campaign_for(fleet, start_time)
    if fleet.campaign_id and campaign is None:
        not_copied.append(NOT_COPIED_CAMPAIGN)

    location_id = None
    if fleet.location_id:
        if fleet.location.fleets_active:
            location_id = fleet.location_id
        else:
            # The form's default staging instead of a dead location.
            not_copied.append(NOT_COPIED_LOCATION)

    open_to_alliance = bool(fleet.open_to_alliance)
    if (
        open_to_alliance
        and fleet.host_group_id
        and not fleet.host_group.allow_open_fleets
    ):
        open_to_alliance = False
        not_copied.append(NOT_COPIED_OPEN_TO_ALLIANCE)

    return CreateEveFleetRequest(
        type=fleet.type,
        description=fleet.description,
        objective=fleet.objective or None,
        start_time=start_time,
        doctrine_id=fleet.doctrine_id,
        # Ignored for a group fleet; checked for an alliance fleet.
        audience_id=fleet.audience_id or 0,
        location_id=location_id,
        disable_motd=bool(fleet.disable_motd),
        hide_volunteers=fleet.hide_volunteers,
        campaign_id=campaign.id if campaign else None,
        host_group_id=fleet.host_group_id,
        open_to_alliance=open_to_alliance,
        on_schedule=open_to_alliance and bool(fleet.on_schedule),
        # Invites are never copied: the new fleet starts with nobody asked.
        invite_only=bool(fleet.invite_only),
    )


def copy_fleet_ships(source: EveFleet, copy: EveFleet) -> int:
    """Copy the ships the FC added and their refits; returns ships copied.

    In-game saved fittings belong to the old fleet and are removed when it
    closes, so the copies start without them (``save_copied_fleet_fits``
    saves new ones under the copy's FC).
    """
    new_ids = {}
    for fitting in EveFleetFitting.objects.filter(eve_fleet=source).order_by(
        "order", "id"
    ):
        new_ids[fitting.id] = EveFleetFitting.objects.create(
            eve_fleet=copy,
            fitting_id=fitting.fitting_id,
            name=fitting.name,
            ship_id=fitting.ship_id,
            eft_format=fitting.eft_format,
            role=fitting.role,
            order=fitting.order,
        ).id

    for refit in EveFleetFittingRefit.objects.filter(
        eve_fleet=source
    ).order_by("id"):
        if refit.fleet_fitting_id and refit.fleet_fitting_id not in new_ids:
            continue
        EveFleetFittingRefit.objects.create(
            eve_fleet=copy,
            fitting_id=refit.fitting_id,
            fleet_fitting_id=new_ids.get(refit.fleet_fitting_id),
            refit_id=refit.refit_id,
            name=refit.name,
            cargo_modules=refit.cargo_modules,
            notes=refit.notes,
            eft_format=refit.eft_format,
        )
    EveFleetShipTarget.objects.bulk_create(
        [
            EveFleetShipTarget(
                eve_fleet=copy,
                name=target.name,
                target=target.target,
                order=target.order,
                ship_type_ids=list(target.ship_type_ids or []),
                group_ids=list(target.group_ids or []),
            )
            for target in EveFleetShipTarget.objects.filter(eve_fleet=source)
        ]
    )
    return len(new_ids)


def fits_to_save(fleet: EveFleet) -> list:
    """Custom fits and refits with an EFT that have no in-game copy yet."""
    return [
        *EveFleetFitting.objects.filter(
            eve_fleet=fleet, fitting__isnull=True, esi_fitting_id__isnull=True
        ).exclude(eft_format=""),
        *EveFleetFittingRefit.objects.filter(
            eve_fleet=fleet, esi_fitting_id__isnull=True
        )
        .exclude(eft_format="")
        .select_related("fitting", "fleet_fitting"),
    ]


def save_copied_fits(fleet: EveFleet) -> int:
    """Save the copy's custom fits and refits in-game; returns how many.

    Adding them by hand needs the FC's fittings scope, but a copy never
    fails for want of it: without the scope the MOTD still links every fit,
    and the fits are just not in the FC's fitting window. Safe to run twice.
    """
    # pylint: disable=import-outside-toplevel
    from fleets.helpers.esi_fittings import (
        fitting_publisher,
        publish_and_store,
    )

    if fleet.status in ("complete", "cancelled"):
        return 0
    publisher = fitting_publisher(fleet.created_by)
    if publisher is None:
        return 0
    saved = 0
    for obj in fits_to_save(fleet):
        if isinstance(obj, EveFleetFitting):
            label, kind = obj.name, "fit"
        else:
            label, kind = f"{obj.target_name} → {obj.name}", "refit"
        error = publish_and_store(
            obj, publisher, fleet.id, label, kind, label, obj.eft_format
        )
        if not error:
            saved += 1
    return saved


def copy_fleet(
    *, user: User, source: EveFleet, start_time: datetime
) -> FleetCopy | tuple[int, dict]:
    """Schedule a copy of ``source`` at ``start_time`` with ``user`` as FC."""
    denied = copy_denied(user, source)
    if denied:
        return denied
    if start_time <= timezone.now():
        return 400, ErrorResponse.new("Pick a start time after now")
    if not source.host_group_id and not source.audience_id:
        return 400, ErrorResponse.new(
            "This fleet's audience no longer exists. Schedule a new fleet "
            "instead."
        )

    not_copied: list[str] = []
    payload = _copy_request(source, start_time, not_copied)

    with transaction.atomic():
        result = create_scheduled_fleet(user=user, payload=payload)
        if isinstance(result, tuple):
            transaction.set_rollback(True)
            return result
        copy_fleet_ships(source, result)

    # pylint: disable=import-outside-toplevel
    from fleets.tasks import queue_save_copied_fleet_fits

    queue_save_copied_fleet_fits(result)
    return FleetCopy(fleet=result, not_copied=not_copied)
