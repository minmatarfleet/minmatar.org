"""Typical fleet demand for market contracts from doctrine fleet comps."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from math import ceil
from statistics import median
from typing import Iterable

from django.utils import timezone

from fittings.models import EveDoctrineFitting, EveFitting
from fleets.helpers.member_ships import (
    effective_fleet_ship,
    peak_concurrent_ship_count,
)
from fleets.models import (
    EveFleet,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetInstanceMemberShipSnapshot,
)
from market.helpers.contracts import (
    CONTRACT_BURST_GAP,
    CONTRACT_BURST_LOOKBACK_DAYS,
    finished_contract_burst_size_by_fitting,
)

# How far back to look at doctrine fleets for hull composition / frequency.
FLEET_COMPOSITION_LOOKBACK_DAYS = 90
FLEETS_PER_MONTH_DAYS = 30

# Drop fleets smaller than this fraction of the preliminary median (tiny
# formups / partial comps should not define wipe demand).
_SMALL_FLEET_MEDIAN_FRACTION = 0.5
_MIN_SAMPLES_FOR_OUTLIER_FILTER = 3


@dataclass(frozen=True)
class FittingFleetDemand:
    """Doctrine-fleet demand stats for one market fitting."""

    typical_fleet_size: int | None = None
    fleets_per_month: float | None = None


def estimate_typical_fleet_size(samples: list[int]) -> int | None:
    """Median hull count after dropping small outlier fleets.

    Fleets below ``max(2, ceil(preliminary_median * 0.5))`` are excluded when
    there are enough samples to judge. Falls back to the unfiltered median if
    filtering would remove everything.
    """
    positive = [n for n in samples if n >= 1]
    if not positive:
        return None
    if len(positive) < _MIN_SAMPLES_FOR_OUTLIER_FILTER:
        return max(1, int(median(positive)))

    preliminary = median(positive)
    floor = max(2, int(ceil(preliminary * _SMALL_FLEET_MEDIAN_FRACTION)))
    trimmed = [n for n in positive if n >= floor]
    chosen = trimmed if trimmed else positive
    return max(1, int(median(chosen)))


def _normalize_fleets_per_month(
    fleet_count: int,
    *,
    lookback_days: int,
) -> float | None:
    """Scale a lookback fleet count to a 30-day rate."""
    if fleet_count <= 0 or lookback_days <= 0:
        return None
    return round(fleet_count * FLEETS_PER_MONTH_DAYS / lookback_days, 1)


def _hull_counts_by_fleet_ship(
    *,
    fleet_ids: list[int],
    ship_type_ids: set[int],
) -> dict[tuple[int, int], int]:
    """Peak (or effective final) hull counts per fleet and ship type.

    Prefers peak concurrent counts from ship history snapshots so end-of-fleet
    capsules do not erase doctrine hulls. Falls back to ``effective_fleet_ship``
    when a fleet has no snapshots.
    """
    if not fleet_ids or not ship_type_ids:
        return {}

    instance_rows = list(
        EveFleetInstance.objects.filter(
            eve_fleet_id__in=fleet_ids
        ).values_list("id", "eve_fleet_id")
    )
    fleet_by_instance = {row[0]: row[1] for row in instance_rows}
    instance_ids = list(fleet_by_instance.keys())
    if not instance_ids:
        return {}

    members = list(
        EveFleetInstanceMember.objects.filter(
            eve_fleet_instance_id__in=instance_ids
        ).only(
            "id",
            "eve_fleet_instance_id",
            "ship_type_id",
            "ship_name",
        )
    )
    members_by_fleet: dict[int, list[EveFleetInstanceMember]] = defaultdict(
        list
    )
    member_ids: list[int] = []
    for member in members:
        fleet_id = fleet_by_instance.get(member.eve_fleet_instance_id)
        if fleet_id is None:
            continue
        members_by_fleet[fleet_id].append(member)
        member_ids.append(member.id)

    snapshots = list(
        EveFleetInstanceMemberShipSnapshot.objects.filter(
            member_id__in=member_ids
        )
        .order_by("created_at")
        .values_list("member_id", "ship_type_id", "created_at")
    )
    snaps_by_fleet: dict[int, list[tuple[int, int, object]]] = defaultdict(
        list
    )
    member_fleet = {
        member.id: fleet_by_instance.get(member.eve_fleet_instance_id)
        for member in members
    }
    for member_id, ship_type_id, created_at in snapshots:
        fleet_id = member_fleet.get(member_id)
        if fleet_id is None:
            continue
        snaps_by_fleet[fleet_id].append(
            (member_id, int(ship_type_id), created_at)
        )

    counts: dict[tuple[int, int], int] = {}
    for fleet_id, fleet_members in members_by_fleet.items():
        fleet_snaps = snaps_by_fleet.get(fleet_id) or []
        fleet_member_ids = [m.id for m in fleet_members]
        for ship_type_id in ship_type_ids:
            if fleet_snaps:
                peak = peak_concurrent_ship_count(
                    member_ids=fleet_member_ids,
                    ship_type_id=ship_type_id,
                    snapshots=fleet_snaps,
                )
            else:
                peak = sum(
                    1
                    for member in fleet_members
                    if effective_fleet_ship(member)[0] == ship_type_id
                )
            if peak > 0:
                counts[(fleet_id, ship_type_id)] = peak
    return counts


def fleet_demand_by_fitting(
    *,
    fitting_ids: Iterable[int],
    location=None,
    lookback_days: int = FLEET_COMPOSITION_LOOKBACK_DAYS,
    use_burst_fallback: bool = True,
) -> dict[int, FittingFleetDemand]:
    """Doctrine-fleet demand for each fitting (typical size + monthly rate).

    For fitting F (ship S) in doctrines D: among fleets with doctrine in D,
    take peak concurrent counts of S for typical size, and count fleets where
    S appeared for a 30-day normalized rate.

    When no fleet samples exist and ``use_burst_fallback`` is true, fall back
    to finished-contract purchase bursts at ``location`` for typical size only.
    """
    fitting_id_list = [fid for fid in fitting_ids if fid is not None]
    if not fitting_id_list:
        return {}

    fittings = {
        f.id: f
        for f in EveFitting.objects.filter(pk__in=fitting_id_list).only(
            "id", "ship_id"
        )
    }
    doctrine_ids_by_fitting: dict[int, set[int]] = {
        fid: set() for fid in fitting_id_list
    }
    for fitting_id, doctrine_id in EveDoctrineFitting.objects.filter(
        fitting_id__in=fitting_id_list
    ).values_list("fitting_id", "doctrine_id"):
        doctrine_ids_by_fitting[fitting_id].add(doctrine_id)

    demand: dict[int, FittingFleetDemand] = {
        fid: FittingFleetDemand() for fid in fitting_id_list
    }
    all_doctrine_ids = {
        did for ids in doctrine_ids_by_fitting.values() for did in ids
    }
    if all_doctrine_ids:
        since = timezone.now() - timedelta(days=lookback_days)
        fleet_rows = list(
            EveFleet.objects.filter(
                doctrine_id__in=all_doctrine_ids,
                start_time__gte=since,
            ).values_list("id", "doctrine_id")
        )
        doctrine_by_fleet = {row[0]: row[1] for row in fleet_rows}
        fleet_ids = list(doctrine_by_fleet.keys())

        ship_ids = {
            fittings[fid].ship_id
            for fid in fitting_id_list
            if fid in fittings and fittings[fid].ship_id
        }
        hull_by_fleet_ship = _hull_counts_by_fleet_ship(
            fleet_ids=fleet_ids,
            ship_type_ids=ship_ids,
        )

        fleets_by_doctrine: dict[int, list[int]] = {}
        for fleet_id, doctrine_id in doctrine_by_fleet.items():
            fleets_by_doctrine.setdefault(doctrine_id, []).append(fleet_id)

        for fitting_id in fitting_id_list:
            fitting = fittings.get(fitting_id)
            if fitting is None or not fitting.ship_id:
                continue
            doctrine_ids = doctrine_ids_by_fitting.get(fitting_id) or set()
            if not doctrine_ids:
                continue
            samples: list[int] = []
            fleets_with_ship: set[int] = set()
            for doctrine_id in doctrine_ids:
                for fleet_id in fleets_by_doctrine.get(doctrine_id, []):
                    count = hull_by_fleet_ship.get(
                        (fleet_id, fitting.ship_id), 0
                    )
                    if count >= 1:
                        samples.append(count)
                        fleets_with_ship.add(fleet_id)
            demand[fitting_id] = FittingFleetDemand(
                typical_fleet_size=estimate_typical_fleet_size(samples),
                fleets_per_month=_normalize_fleets_per_month(
                    len(fleets_with_ship),
                    lookback_days=lookback_days,
                ),
            )

    missing = [
        fid for fid, row in demand.items() if row.typical_fleet_size is None
    ]
    if use_burst_fallback and missing and location is not None:
        burst_sizes = finished_contract_burst_size_by_fitting(
            location=location,
            fitting_ids=missing,
            lookback_days=CONTRACT_BURST_LOOKBACK_DAYS,
            gap=CONTRACT_BURST_GAP,
        )
        for fitting_id, size in burst_sizes.items():
            prior = demand.get(fitting_id, FittingFleetDemand())
            demand[fitting_id] = FittingFleetDemand(
                typical_fleet_size=size,
                fleets_per_month=prior.fleets_per_month,
            )

    return {
        fid: row
        for fid, row in demand.items()
        if row.typical_fleet_size is not None
        or row.fleets_per_month is not None
    }


def typical_fleet_size_by_fitting(
    *,
    fitting_ids: Iterable[int],
    location=None,
    lookback_days: int = FLEET_COMPOSITION_LOOKBACK_DAYS,
    use_burst_fallback: bool = True,
) -> dict[int, int]:
    """Median hulls of each fitting's ship on recent doctrine fleets."""
    return {
        fitting_id: demand.typical_fleet_size
        for fitting_id, demand in fleet_demand_by_fitting(
            fitting_ids=fitting_ids,
            location=location,
            lookback_days=lookback_days,
            use_burst_fallback=use_burst_fallback,
        ).items()
        if demand.typical_fleet_size is not None
    }
