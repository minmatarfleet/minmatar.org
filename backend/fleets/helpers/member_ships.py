"""Append-only ship history for fleet instance members."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fleets.models import (
        EveFleetInstance,
        EveFleetInstanceMember,
        EveFleetInstanceMemberShipSnapshot,
    )

CAPSULE_TYPE_ID = 670


def _fleet_models():
    # Defer import to avoid circular import (fleets.models imports this module).
    from fleets.models import (  # pylint: disable=import-outside-toplevel
        EveFleetInstanceMember,
        EveFleetInstanceMemberShipSnapshot,
    )

    return EveFleetInstanceMember, EveFleetInstanceMemberShipSnapshot


def _last_snapshot(
    member: EveFleetInstanceMember,
) -> EveFleetInstanceMemberShipSnapshot | None:
    _, ship_snapshot_model = _fleet_models()
    return (
        ship_snapshot_model.objects.filter(member=member)
        .order_by("-created_at")
        .first()
    )


def _create_ship_snapshot(
    member: EveFleetInstanceMember,
    *,
    ship_type_id: int,
    ship_name: str,
    solar_system_id: int,
    solar_system_name: str,
) -> EveFleetInstanceMemberShipSnapshot:
    _, ship_snapshot_model = _fleet_models()
    return ship_snapshot_model.objects.create(
        member=member,
        ship_type_id=ship_type_id,
        ship_name=ship_name,
        solar_system_id=solar_system_id,
        solar_system_name=solar_system_name,
    )


def record_initial_ship_snapshot(
    member: EveFleetInstanceMember,
    *,
    ship_type_id: int,
    ship_name: str,
    solar_system_id: int,
    solar_system_name: str,
) -> EveFleetInstanceMemberShipSnapshot | None:
    """Record the first ship observed when a member joins the fleet."""
    _, ship_snapshot_model = _fleet_models()
    if ship_snapshot_model.objects.filter(member=member).exists():
        return None
    return _create_ship_snapshot(
        member,
        ship_type_id=ship_type_id,
        ship_name=ship_name,
        solar_system_id=solar_system_id,
        solar_system_name=solar_system_name,
    )


def record_ship_snapshots_for_change(
    member: EveFleetInstanceMember,
    *,
    previous_ship_type_id: int,
    previous_ship_name: str,
    previous_solar_system_id: int,
    previous_solar_system_name: str,
    new_ship_type_id: int,
    new_ship_name: str,
    new_solar_system_id: int,
    new_solar_system_name: str,
) -> list[EveFleetInstanceMemberShipSnapshot]:
    """Append ship snapshots when ESI reports a ship change."""
    created: list[EveFleetInstanceMemberShipSnapshot] = []
    last = _last_snapshot(member)

    if previous_ship_type_id == new_ship_type_id:
        if last is None:
            snapshot = _create_ship_snapshot(
                member,
                ship_type_id=new_ship_type_id,
                ship_name=new_ship_name,
                solar_system_id=new_solar_system_id,
                solar_system_name=new_solar_system_name,
            )
            created.append(snapshot)
        return created

    if last is None or last.ship_type_id != previous_ship_type_id:
        created.append(
            _create_ship_snapshot(
                member,
                ship_type_id=previous_ship_type_id,
                ship_name=previous_ship_name,
                solar_system_id=previous_solar_system_id,
                solar_system_name=previous_solar_system_name,
            )
        )

    last = _last_snapshot(member)
    if last is None or last.ship_type_id != new_ship_type_id:
        created.append(
            _create_ship_snapshot(
                member,
                ship_type_id=new_ship_type_id,
                ship_name=new_ship_name,
                solar_system_id=new_solar_system_id,
                solar_system_name=new_solar_system_name,
            )
        )

    return created


def last_non_capsule_ship_snapshot(
    member: EveFleetInstanceMember,
) -> EveFleetInstanceMemberShipSnapshot | None:
    """Most recent ship snapshot that is not a capsule."""
    _, ship_snapshot_model = _fleet_models()
    return (
        ship_snapshot_model.objects.filter(member=member)
        .exclude(ship_type_id=CAPSULE_TYPE_ID)
        .order_by("-created_at")
        .first()
    )


def effective_fleet_ship(
    member: EveFleetInstanceMember,
) -> tuple[int, str]:
    """
    Ship to attribute for fleet analysis when a pilot may have been podded.

    Returns the member's current ship unless they are in a capsule, in which
    case the most recent non-capsule snapshot is used when available.
    """
    if member.ship_type_id != CAPSULE_TYPE_ID:
        return member.ship_type_id, member.ship_name

    prior = last_non_capsule_ship_snapshot(member)
    if prior:
        return prior.ship_type_id, prior.ship_name

    return member.ship_type_id, member.ship_name


def apply_esi_fleet_member(
    fleet_instance: EveFleetInstance,
    esi_fleet_member: dict,
    resolved_ids: dict[int, str],
) -> EveFleetInstanceMember:
    """Create or update a fleet member row and append ship history as needed."""
    member_model, _ = _fleet_models()
    character_id = esi_fleet_member["character_id"]
    ship_type_id = esi_fleet_member["ship_type_id"]
    solar_system_id = esi_fleet_member["solar_system_id"]
    ship_name = resolved_ids[ship_type_id]
    solar_system_name = resolved_ids[solar_system_id]

    member_fields = {
        "join_time": esi_fleet_member["join_time"],
        "role": esi_fleet_member["role"],
        "role_name": esi_fleet_member["role_name"],
        "ship_type_id": ship_type_id,
        "ship_name": ship_name,
        "solar_system_id": solar_system_id,
        "solar_system_name": solar_system_name,
        "squad_id": esi_fleet_member["squad_id"],
        "station_id": esi_fleet_member["station_id"],
        "takes_fleet_warp": esi_fleet_member["takes_fleet_warp"],
        "wing_id": esi_fleet_member["wing_id"],
        "character_name": resolved_ids[character_id],
    }

    existing = member_model.objects.filter(
        eve_fleet_instance=fleet_instance,
        character_id=character_id,
    ).first()

    if existing:
        record_ship_snapshots_for_change(
            existing,
            previous_ship_type_id=existing.ship_type_id,
            previous_ship_name=existing.ship_name,
            previous_solar_system_id=existing.solar_system_id,
            previous_solar_system_name=existing.solar_system_name,
            new_ship_type_id=ship_type_id,
            new_ship_name=ship_name,
            new_solar_system_id=solar_system_id,
            new_solar_system_name=solar_system_name,
        )
        for field, value in member_fields.items():
            setattr(existing, field, value)
        existing.save()
        return existing

    member = member_model.objects.create(
        eve_fleet_instance=fleet_instance,
        character_id=character_id,
        **member_fields,
    )
    record_initial_ship_snapshot(
        member,
        ship_type_id=ship_type_id,
        ship_name=ship_name,
        solar_system_id=solar_system_id,
        solar_system_name=solar_system_name,
    )
    return member
