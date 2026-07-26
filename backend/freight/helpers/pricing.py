"""Freight route reward / cost formulas."""

from __future__ import annotations

import math
from typing import Union

from freight.models import EveFreightRoute


def route_cost_isk(
    route: EveFreightRoute,
    m3: Union[int, float],
    collateral: int = 0,
) -> int:
    """
    Courier reward for a route.

    Matches ``GET /api/freight/routes/{id}/cost``:
    ``isk_per_m3 * m3 + ceil(collateral_modifier * collateral)``.
    """
    volume = max(0, int(m3))
    coll = max(0, int(collateral))
    return int(route.isk_per_m3) * volume + math.ceil(
        float(route.collateral_modifier) * coll
    )
