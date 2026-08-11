"""Freight route reward / cost formulas."""

from __future__ import annotations

import math
from typing import Optional, Union

from freight.models import EveFreightRoute

# Default max volume for rate routes (UI / API exposure).
STANDARD_MAX_M3 = 350_000


class FreightContractValidationError(ValueError):
    """Contract volume or collateral exceeds the route limits."""


def route_max_m3(route: EveFreightRoute) -> Optional[int]:
    """Effective max m³ for API/UI. Rate routes use STANDARD_MAX_M3."""
    if route.route_type == EveFreightRoute.RouteType.FIXED:
        return route.max_m3
    return STANDARD_MAX_M3


def route_max_collateral(route: EveFreightRoute) -> Optional[int]:
    """Effective max collateral for API/UI. Rate routes have no cap."""
    if route.route_type == EveFreightRoute.RouteType.FIXED:
        return route.max_collateral
    return None


def validate_route_contract(
    route: EveFreightRoute,
    m3: Union[int, float],
    collateral: int = 0,
) -> None:
    """
    Reject contracts that exceed fixed-route limits.

    Raises FreightContractValidationError with a clear message.
    """
    if route.route_type != EveFreightRoute.RouteType.FIXED:
        return

    volume = max(0, int(m3))
    coll = max(0, int(collateral))

    if route.max_m3 is not None and volume > route.max_m3:
        raise FreightContractValidationError(
            f"Volume {volume} m³ exceeds route maximum of {route.max_m3} m³."
        )
    if route.max_collateral is not None and coll > route.max_collateral:
        raise FreightContractValidationError(
            f"Collateral {coll} ISK exceeds route maximum of "
            f"{route.max_collateral} ISK."
        )


def route_cost_isk(
    route: EveFreightRoute,
    m3: Union[int, float],
    collateral: int = 0,
) -> int:
    """
    Courier reward for a route.

    Rate: ``isk_per_m3 * m3 + ceil(collateral_modifier * collateral)``.
    Fixed: ``fixed_fee_millions * 1_000_000`` (volume/collateral ignored).
    """
    if route.route_type == EveFreightRoute.RouteType.FIXED:
        return int(float(route.fixed_fee_millions) * 1_000_000)

    volume = max(0, int(m3))
    coll = max(0, int(collateral))
    return int(route.isk_per_m3) * volume + math.ceil(
        float(route.collateral_modifier) * coll
    )
