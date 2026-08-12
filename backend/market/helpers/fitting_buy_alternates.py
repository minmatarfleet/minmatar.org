"""Shopping-list alternate modules for fitting buy orders."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

from eveuniverse.models import EveType, EveTypeDogmaAttribute

from fittings.helpers.module_substitutions import variant_types_for
from fittings.models import EveFittingModuleSubstitution
from market.helpers.item_classification import (
    ITEM_VARIANT_DEADSPACE,
    ITEM_VARIANT_FACTION,
    ITEM_VARIANT_T1,
    ITEM_VARIANT_T2,
    classify_items,
)

# Practical Multibuy swaps: T1 meta (Compact/Enduring), T2, faction, deadspace.
# Exclude officer + named/storyline (classified as "other").
SHOPPING_ALTERNATE_VARIANTS = frozenset(
    {
        ITEM_VARIANT_T1,
        ITEM_VARIANT_T2,
        ITEM_VARIANT_FACTION,
        ITEM_VARIANT_DEADSPACE,
    }
)

_VARIANT_SORT = {
    ITEM_VARIANT_T2: 0,
    ITEM_VARIANT_FACTION: 1,
    ITEM_VARIANT_DEADSPACE: 2,
    ITEM_VARIANT_T1: 3,
}

DOGMA_CPU_ID = 50
DOGMA_POWER_ID = 30
PRICE_CAP_RATIO = Decimal("1.5")


def listed_substitutes_by_preferred(
    fitting_ids: Iterable[int],
) -> dict[int, set[int]]:
    """preferred_type_id → substitute type ids listed on those fittings."""
    result: dict[int, set[int]] = defaultdict(set)
    ids = list({int(fid) for fid in fitting_ids if fid})
    if not ids:
        return {}
    for (
        preferred_id,
        substitute_id,
    ) in EveFittingModuleSubstitution.objects.filter(
        fitting_id__in=ids
    ).values_list(
        "preferred_module_id", "substitute_module_id"
    ):
        result[int(preferred_id)].add(int(substitute_id))
    return dict(result)


def cpu_pg_by_type(
    type_ids: Iterable[int],
) -> dict[int, tuple[float | None, float | None]]:
    ids = list({int(tid) for tid in type_ids if tid})
    result: dict[int, tuple[float | None, float | None]] = {
        tid: (None, None) for tid in ids
    }
    if not ids:
        return result
    for row in EveTypeDogmaAttribute.objects.filter(
        eve_type_id__in=ids,
        eve_dogma_attribute_id__in=(DOGMA_CPU_ID, DOGMA_POWER_ID),
    ).values("eve_type_id", "eve_dogma_attribute_id", "value"):
        cpu, pg = result[row["eve_type_id"]]
        value = float(row["value"])
        if row["eve_dogma_attribute_id"] == DOGMA_CPU_ID:
            cpu = value
        else:
            pg = value
        result[row["eve_type_id"]] = (cpu, pg)
    return result


def cpu_pg_fits(
    preferred: tuple[float | None, float | None],
    candidate: tuple[float | None, float | None],
) -> bool:
    """True when candidate CPU and PG are both present and ≤ preferred.

    Missing dogma on either side is not treated as equal/better.
    """
    p_cpu, p_pg = preferred
    c_cpu, c_pg = candidate
    if p_cpu is None or p_pg is None or c_cpu is None or c_pg is None:
        return False
    return c_cpu <= p_cpu and c_pg <= p_pg


def parse_jita_sell_min(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if number <= 0:
        return None
    return number


def price_within_cap(preferred_min, candidate_min) -> bool:
    """False when candidate Jita sell min is ≥ 1.5× preferred.

    Missing or unknown prices are not excluded.
    """
    preferred = parse_jita_sell_min(preferred_min)
    candidate = parse_jita_sell_min(candidate_min)
    if preferred is None or candidate is None:
        return True
    return candidate < preferred * PRICE_CAP_RATIO


def shopping_alternate_types_for(
    eve_type: EveType,
    *,
    limit: int = 20,
    listed_substitute_ids: set[int] | None = None,
    jita_sell_min_by_type: (
        dict[int, Decimal | float | str | None] | None
    ) = None,
) -> list[EveType]:
    """
    Same-family variants suitable for fitting Multibuy swaps.

    Keeps T2 / faction / deadspace / T1; drops officer and named/storyline.
    Requires candidate CPU and PG ≤ preferred unless listed on the fitting.
    Drops candidates priced ≥ 1.5× the preferred Jita sell min.
    """
    candidates = list(variant_types_for(eve_type).only("id", "name"))
    if not candidates:
        return []

    classified = classify_items(row.id for row in candidates)
    family: list[EveType] = []
    for row in candidates:
        variant = classified.get(row.id)
        if variant is None:
            continue
        if variant.item_variant not in SHOPPING_ALTERNATE_VARIANTS:
            continue
        family.append(row)
    if not family:
        return []

    listed = listed_substitute_ids or set()
    prices = jita_sell_min_by_type or {}
    preferred_min = prices.get(eve_type.id)
    fits = cpu_pg_by_type([eve_type.id, *(row.id for row in family)])
    preferred_fit = fits.get(eve_type.id, (None, None))
    filtered: list[tuple[int, str, EveType]] = []
    for row in family:
        allowed = cpu_pg_fits(
            preferred_fit, fits.get(row.id, (None, None))
        ) or (row.id in listed)
        if not allowed:
            continue
        if not price_within_cap(preferred_min, prices.get(row.id)):
            continue
        variant = classified[row.id]
        filtered.append(
            (
                _VARIANT_SORT.get(variant.item_variant, 99),
                row.name or "",
                row,
            )
        )
    filtered.sort(key=lambda entry: (entry[0], entry[1]))
    return [row for _, _, row in filtered[:limit]]
