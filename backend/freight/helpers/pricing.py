"""Freight route reward / cost formulas."""

from __future__ import annotations

import math
from typing import Optional, Union

from freight.models import EveFreightRoute

# Default max volume for rate routes (UI / API exposure), and the volume
# above which a fixed route also charges its XL cargo fee.
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


def _millions_to_isk(millions: Union[int, float]) -> int:
    """Convert a fee expressed in millions of ISK to whole ISK."""
    # Rounded rather than truncated: 2.9 * 1_000_000 is 2899999.9999999995
    # in binary floating point, which would truncate to one ISK short.
    return round(float(millions) * 1_000_000)


def route_cost_isk(
    route: EveFreightRoute,
    m3: Union[int, float],
    collateral: int = 0,
) -> int:
    """
    Courier reward for a route.

    Rate: ``isk_per_m3 * m3 + ceil(collateral_modifier * collateral)``.
    Fixed: ``fixed_fee_millions + xl_fee_millions (when volume exceeds
    STANDARD_MAX_M3) + ceil(collateral_modifier * collateral)``.
    """
    volume = max(0, int(m3))
    coll = max(0, int(collateral))
    collateral_fee = math.ceil(float(route.collateral_modifier) * coll)

    if route.route_type == EveFreightRoute.RouteType.FIXED:
        reward = _millions_to_isk(route.fixed_fee_millions)
        if volume > STANDARD_MAX_M3:
            reward += _millions_to_isk(route.xl_fee_millions)
        return reward + collateral_fee

    return int(route.isk_per_m3) * volume + collateral_fee
