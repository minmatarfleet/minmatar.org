"""
Estimate alliance freight cost for planner shopping lists.

Looks up an active ``EveFreightRoute`` from the price-baseline hub (Jita)
into the selected facility solar system. Cost uses the same formula as the
freight calculator: ISK/m³ × volume + collateral %.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

from eveonline.models import EveLocation
from eveuniverse.models import EveType

from freight.helpers.pricing import route_cost_isk
from freight.models import EveFreightRoute
from industry.helpers.compressed_ore import compressed_volume_m3
from industry.helpers.facility_profiles import get_facility_system_id


@dataclass(frozen=True)
class FreightEstimate:
    volume_m3: float
    billable_m3: int
    freight_isk: int
    route_id: Optional[int] = None
    route_label: Optional[str] = None
    collateral_isk: int = 0

    @property
    def has_route(self) -> bool:
        return self.route_id is not None


def eve_type_volume_m3(eve_type: EveType) -> float:
    """Packaged volume when set, else unpackaged volume (m³)."""
    packaged = getattr(eve_type, "packaged_volume", None)
    if packaged is not None and float(packaged) > 0:
        return float(packaged)
    volume = getattr(eve_type, "volume", None)
    if volume is not None and float(volume) > 0:
        return float(volume)
    return 0.0


def materials_volume_m3_from_type_qtys(
    type_qtys: Sequence[Tuple[int, int]],
) -> float:
    """Total cargo m³ for (type_id, qty) rows."""
    if not type_qtys:
        return 0.0
    ids = [int(tid) for tid, _ in type_qtys if tid]
    volumes = {
        int(tid): eve_type_volume_m3(eve_type)
        for tid, eve_type in EveType.objects.filter(id__in=ids)
        .in_bulk()
        .items()
    }
    total = 0.0
    for tid, qty in type_qtys:
        if qty <= 0:
            continue
        total += int(qty) * float(volumes.get(int(tid), 0.0))
    return total


def materials_volume_m3_from_named(named_qtys: Dict[str, int]) -> float:
    """Total cargo m³ for name→qty maps (compressed Multibuy imports)."""
    if not named_qtys:
        return 0.0
    names = list(named_qtys.keys())
    types_by_name = {t.name: t for t in EveType.objects.filter(name__in=names)}
    total = 0.0
    for name, qty in named_qtys.items():
        if qty <= 0:
            continue
        eve_type = types_by_name.get(name)
        per_unit = eve_type_volume_m3(eve_type) if eve_type else 0.0
        if per_unit <= 0:
            # Ranking table is per base ore; unknown ores return 1.0 — only
            # use when the name looks like compressed ore.
            if name.startswith("Compressed "):
                per_unit = compressed_volume_m3(name)
        total += int(qty) * per_unit
    return total


def find_inbound_freight_route(
    facility_key: str,
) -> Optional[EveFreightRoute]:
    """
    Active route from the price-baseline hub into the facility system.

    Returns None when no matching route exists (do not invent rates).
    """
    try:
        dest_system_id = get_facility_system_id(facility_key)
    except ValueError:
        return None

    qs = EveFreightRoute.objects.filter(
        active=True,
        destination_location__solar_system_id=dest_system_id,
    ).select_related("origin_location", "destination_location")

    baseline = EveLocation.objects.filter(price_baseline=True).first()
    if baseline is None:
        return None

    preferred = qs.filter(origin_location=baseline).first()
    if preferred is not None:
        return preferred
    return qs.filter(
        origin_location__solar_system_id=baseline.solar_system_id
    ).first()


def _route_label(route: EveFreightRoute) -> str:
    origin = (
        route.origin_location.short_name
        if route.origin_location
        else "Unknown"
    )
    dest = (
        route.destination_location.short_name
        if route.destination_location
        else "Unknown"
    )
    return f"{origin} → {dest}"


def estimate_freight_cost(
    *,
    facility_key: str,
    volume_m3: float,
    collateral_isk: int,
) -> FreightEstimate:
    """Apply route pricing to a cargo volume + collateral, or zero if no route."""
    volume = max(0.0, float(volume_m3))
    billable = int(math.ceil(volume)) if volume > 0 else 0
    collateral = max(0, int(collateral_isk))
    route = find_inbound_freight_route(facility_key)
    if route is None:
        return FreightEstimate(
            volume_m3=volume,
            billable_m3=billable,
            freight_isk=0,
            collateral_isk=collateral,
        )
    cost = route_cost_isk(route, billable, collateral)
    return FreightEstimate(
        volume_m3=volume,
        billable_m3=billable,
        freight_isk=cost,
        route_id=route.id,
        route_label=_route_label(route),
        collateral_isk=collateral,
    )


def estimate_plan_freight(
    *,
    facility_key: str,
    type_qtys: Optional[Sequence[Tuple[int, int]]] = None,
    named_qtys: Optional[Dict[str, int]] = None,
    collateral_isk: int,
) -> FreightEstimate:
    """Volume from type qtys or named Multibuy lines, then route cost."""
    if named_qtys is not None:
        volume = materials_volume_m3_from_named(named_qtys)
    else:
        volume = materials_volume_m3_from_type_qtys(type_qtys or [])
    return estimate_freight_cost(
        facility_key=facility_key,
        volume_m3=volume,
        collateral_isk=collateral_isk,
    )
