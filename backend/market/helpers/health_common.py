"""Shared helpers for market contract / sell-order health builders."""

from __future__ import annotations

from django.db.models import (
    Case,
    F,
    IntegerField,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce

from eveonline.models import EveLocation
from market.helpers.pricing import (
    get_prices_by_type_id,
    get_volume_weighted_average_by_type_id,
)

CRITICAL_RATIO = 0.5

VOLUME_DAYS_1 = 1
VOLUME_DAYS_3 = 3
VOLUME_DAYS_7 = 7
VOLUME_DAYS_30 = 30
VOLUME_DAYS_90 = 90  # inferred-sale retention window

# Match admin sell-order markup bands (sell_orders.MARKUP_*).
MARKUP_UNDERPRICED_MAX = -5
MARKUP_NORMAL_MAX = 5

UNDERSTOCKED_DAYS = 7

FLAG_OUT_OF_STOCK = "out_of_stock"
FLAG_UNDERSTOCKED = "understocked"
FLAG_IN_STOCK = "in_stock"
FLAG_OVERSTOCKED = "overstocked"
FLAG_UNDERPRICED = "underpriced"
FLAG_OVERPRICED = "overpriced"


def windowed_quantity_sum(since, *, field_name: str = "quantity"):
    """Annotate helper: sum field_name for rows with inferred_at >= since."""
    return Coalesce(
        Sum(
            Case(
                When(inferred_at__gte=since, then=F(field_name)),
                default=0,
                output_field=IntegerField(),
            )
        ),
        Value(0),
    )


def windowed_count(since, *, timestamp_field: str = "completed_at"):
    """Annotate helper: count rows with timestamp_field >= since."""
    return Coalesce(
        Sum(
            Case(
                When(**{f"{timestamp_field}__gte": since}, then=1),
                default=0,
                output_field=IntegerField(),
            )
        ),
        Value(0),
    )


def forge_baseline_by_type(type_ids: list[int]) -> dict[int, int]:
    """
    Forge guide for markup/viability: 7d volume-weighted average,
    falling back to latest-day history when a type has no 7d rows.
    """
    if not type_ids:
        return {}
    baseline = get_volume_weighted_average_by_type_id(
        type_ids, days=VOLUME_DAYS_7
    )
    missing = [tid for tid in type_ids if tid not in baseline]
    if missing:
        baseline = {**baseline, **get_prices_by_type_id(missing)}
    return baseline


def fitting_baseline_isk(
    type_quantities: dict[int, int],
    baseline_by_type: dict[int, int],
) -> int | None:
    """
    Sum of type qty × Forge baseline (EFT or contract contents).

    Returns None when no constituent has a usable baseline (fail-open for
    is_price_viable). Partial coverage still prices what we can.
    """
    total = 0
    priced = False
    for type_id, qty in type_quantities.items():
        unit = baseline_by_type.get(type_id)
        if unit is None or unit <= 0:
            continue
        total += int(qty) * int(unit)
        priced = True
    return total if priced else None


def days_of_stock(current_quantity: int, weekly_units: int) -> float | None:
    """Listed qty ÷ 7-day avg daily sales; None when there is no sales rate."""
    if weekly_units <= 0:
        return None
    return round(current_quantity / (weekly_units / float(VOLUME_DAYS_7)), 1)


def sell_gap_flags(
    current: int,
    expected: int,
    avg_markup_pct: float | None,
    days_of_stock_value: float | None,
) -> list[str]:
    flags: list[str] = []
    if current == 0:
        flags.append(FLAG_OUT_OF_STOCK)
    elif (
        days_of_stock_value is not None
        and days_of_stock_value < UNDERSTOCKED_DAYS
    ):
        flags.append(FLAG_UNDERSTOCKED)
    else:
        flags.append(FLAG_IN_STOCK)
        if current > expected:
            flags.append(FLAG_OVERSTOCKED)
    if avg_markup_pct is not None:
        if avg_markup_pct < MARKUP_UNDERPRICED_MAX:
            flags.append(FLAG_UNDERPRICED)
        elif avg_markup_pct > MARKUP_NORMAL_MAX:
            flags.append(FLAG_OVERPRICED)
    return flags


# Matches frontend SHIP_TYPES_SORTED — small hulls first.
SHIP_GROUP_ORDER = [
    "Frigate",
    "Electronic Attack Ship",
    "Assault Frigate",
    "Logistics Frigate",
    "Covert Ops",
    "Stealth Bomber",
    "Interceptor",
    "Destroyer",
    "Interdictor",
    "Command Destroyer",
    "Tactical Destroyer",
    "Cruiser",
    "Heavy Assault Cruiser",
    "Heavy Interdiction Cruiser",
    "Logistics",
    "Logistics Crusiers",
    "Strategic Cruiser",
    "Recon Ship",
    "Force Recon Ship",
    "Combat Recon Ship",
    "Battlecruiser",
    "Combat Battlecruiser",
    "Attack Battlecruiser",
    "Command Ship",
    "Battleship",
    "Marauder",
    "Black Ops",
    "Capital",
    "Dreadnought",
    "Lancer Dreadnought",
    "Carrier",
    "Force Auxiliary",
    "Super Capital",
    "Super Carrier",
    "Titan",
    "Mining Frigate",
    "Expedition Frigate",
    "Mining Barge",
    "Industrial",
    "Transport Ship",
    "Freighter",
    "Jump Freighters",
    "Industrial Command Ship",
    "Unclassified",
]


def ship_size_rank(group_name: str | None) -> int:
    if not group_name:
        return len(SHIP_GROUP_ORDER)
    try:
        return SHIP_GROUP_ORDER.index(group_name)
    except ValueError:
        return len(SHIP_GROUP_ORDER)


def market_active_locations(
    location_id: int | None = None,
) -> list[EveLocation]:
    locations = EveLocation.objects.filter(market_active=True)
    if location_id is not None:
        locations = locations.filter(location_id=location_id)
    return list(locations)


def health_pct(fill_ratios: list[float]) -> float | None:
    if not fill_ratios:
        return None
    return round(100.0 * sum(fill_ratios) / len(fill_ratios), 1)


def summary_fields(source) -> dict:
    if isinstance(source, dict):
        return {
            "health_pct": source["health_pct"],
            "viability_pct": source["viability_pct"],
            "targets": source["targets"],
            "listed_targets": source.get("listed_targets", 0),
            "fulfilled": source["fulfilled"],
            "viable_fulfilled": source["viable_fulfilled"],
            "isk": source["isk"],
            "synced_at": source.get("synced_at"),
            "history_days": source["history_days"],
        }
    return {
        "health_pct": source.health_pct,
        "viability_pct": source.viability_pct,
        "targets": source.targets,
        "listed_targets": source.listed_targets,
        "fulfilled": source.fulfilled,
        "viable_fulfilled": source.viable_fulfilled,
        "isk": source.isk,
        "synced_at": (
            source.synced_at.isoformat() if source.synced_at else None
        ),
        "history_days": source.history_days,
    }
