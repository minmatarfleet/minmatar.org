from __future__ import annotations

import math

from eveuniverse.models import EveSolarSystem

from feed.constants import METERS_PER_LIGHT_YEAR


def _system_position(
    solar_system_id: int,
) -> tuple[float, float, float] | None:
    system = EveSolarSystem.objects.filter(id=solar_system_id).first()
    if system is None:
        system, _ = EveSolarSystem.objects.get_or_create_esi(
            id=solar_system_id
        )
    if (
        system.position_x is None
        or system.position_y is None
        or system.position_z is None
    ):
        return None
    return system.position_x, system.position_y, system.position_z


def light_years_between_systems(
    origin_system_id: int,
    target_system_id: int,
) -> float | None:
    """Euclidean distance in light-years between two solar systems."""
    if origin_system_id == target_system_id:
        return 0.0

    origin = _system_position(origin_system_id)
    target = _system_position(target_system_id)
    if origin is None or target is None:
        return None

    dx = target[0] - origin[0]
    dy = target[1] - origin[1]
    dz = target[2] - origin[2]
    meters = math.sqrt(dx * dx + dy * dy + dz * dz)
    return meters / METERS_PER_LIGHT_YEAR
