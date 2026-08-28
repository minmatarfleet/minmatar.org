"""Match a purchase paste against remaining buyback contract stock."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from eveonline.models import EveCharacter
from eveuniverse.models import EveType

from buyback.helpers.classify import (
    BuybackCategory,
    classify_eve_type,
    resolve_types_by_name,
)
from buyback.helpers.ore_names import compressed_buyback_ore_base
from buyback.helpers.paste import parse_eve_paste
from buyback.helpers.purchase_refine import (
    PurchaseRefine,
    build_purchase_refine,
)
from buyback.helpers.remaining import remaining_sale_quantities
from buyback.helpers.sell_pricing import (
    contract_total_isk,
    line_total,
    unit_prices_for_types,
)
from buyback.models import EveBuybackSettings
from industry.helpers.compressed_ore import (
    MINERAL_NAMES,
    PRIMARY_BELT_ORE_FOR_MINERAL,
    ore_reprocessing_yields,
)


def _ore_yields(name: str, refine_rate: float) -> dict[str, float]:
    """Yields for a hangar ore type, using the family name for graded variants."""
    family = compressed_buyback_ore_base(name)
    lookup = f"Compressed {family}" if family else name
    return ore_reprocessing_yields(lookup, refine_rate=refine_rate)


@dataclass
class FillPick:
    type_id: int
    name: str
    quantity: int
    fill_source: str
    unit_price: float | None
    line_total: float | None


@dataclass
class FillShortfall:
    name: str
    quantity: int
    type_id: int | None = None


@dataclass
class PurchaseFill:
    picks: list[FillPick] = field(default_factory=list)
    shortfalls: list[FillShortfall] = field(default_factory=list)
    unresolved_names: list[str] = field(default_factory=list)
    janice_tsv: str = ""
    shortfall_tsv: str = ""
    contract_total: int = 0
    refine_rate: float = 0.0
    refine_rate_source: str = ""
    facility_key: str = ""
    facility_name: str = ""
    sell_price_basis: str = ""
    sell_markup: float = 0.0


def _tsv(rows: list[tuple[str, int]]) -> str:
    return "\r\n".join(f"{name}\t{qty}" for name, qty in rows if qty > 0)


def _add_pick(picks: dict[int, FillPick], pick: FillPick) -> None:
    existing = picks.get(pick.type_id)
    if existing is None:
        picks[pick.type_id] = pick
        return
    existing.quantity += pick.quantity
    if pick.fill_source == "refine":
        existing.fill_source = "refine"


def _credit_minerals(
    remaining_minerals: dict[str, int],
    outputs: dict[str, float],
    quantity: int,
) -> None:
    for name, per_unit in outputs.items():
        if name not in remaining_minerals or per_unit <= 0:
            continue
        credited = int(math.floor(per_unit * quantity))
        if credited <= 0:
            continue
        remaining_minerals[name] = max(0, remaining_minerals[name] - credited)


def _allocate_ore_for_minerals(
    remaining: dict[int, int],
    lots: dict[int, EveType],
    remaining_minerals: dict[str, int],
    refine: PurchaseRefine,
    picks: dict[int, FillPick],
) -> None:
    ore_lots: list[tuple[int, EveType, dict[str, float]]] = []
    for type_id, eve_type in lots.items():
        if remaining.get(type_id, 0) <= 0:
            continue
        if classify_eve_type(eve_type).category != BuybackCategory.ORE:
            continue
        yields = _ore_yields(eve_type.name, refine.rate_for_ore(eve_type.name))
        mineral_yields = {
            name: qty
            for name, qty in yields.items()
            if name in MINERAL_NAMES and qty > 0
        }
        if mineral_yields:
            ore_lots.append((type_id, eve_type, mineral_yields))

    while True:
        remaining_minerals_positive = {
            name: qty for name, qty in remaining_minerals.items() if qty > 0
        }
        if not remaining_minerals_positive:
            return
        mineral = max(
            remaining_minerals_positive,
            key=lambda name: remaining_minerals_positive[name],
        )
        need = remaining_minerals[mineral]
        preferred = PRIMARY_BELT_ORE_FOR_MINERAL.get(mineral)
        ranked: list[tuple[tuple, int, EveType, dict[str, float]]] = []
        for type_id, eve_type, yields in ore_lots:
            on_hand = remaining.get(type_id, 0)
            per_unit = yields.get(mineral, 0.0)
            if on_hand <= 0 or per_unit <= 0:
                continue
            base = compressed_buyback_ore_base(eve_type.name)
            ranked.append(
                (
                    (
                        0 if base == preferred else 1,
                        -per_unit,
                        eve_type.name,
                    ),
                    type_id,
                    eve_type,
                    yields,
                )
            )
        if not ranked:
            return
        ranked.sort(key=lambda row: row[0])
        _, type_id, eve_type, yields = ranked[0]
        per_unit = yields[mineral]
        take = min(
            remaining[type_id],
            max(1, math.ceil(need / per_unit)),
        )
        remaining[type_id] -= take
        _add_pick(
            picks,
            FillPick(
                type_id=type_id,
                name=eve_type.name,
                quantity=take,
                fill_source="refine",
                unit_price=None,
                line_total=None,
            ),
        )
        _credit_minerals(remaining_minerals, yields, take)


def fill_purchase(  # noqa: C901
    paste: str,
    *,
    settings: EveBuybackSettings | None = None,
    exclude_order_id: int | None = None,
    character: EveCharacter | None = None,
    facility_key: str | None = None,
    use_reprocessing_implants: bool = False,
) -> PurchaseFill:
    """Turn an EVE paste into hangar picks vs leftover demand."""
    loaded = settings or EveBuybackSettings.load()
    refine = build_purchase_refine(
        settings=loaded,
        character=character,
        facility_key=facility_key,
        use_reprocessing_implants=use_reprocessing_implants,
    )
    result = PurchaseFill(
        refine_rate=refine.refine_rate,
        refine_rate_source=refine.refine_rate_source,
        facility_key=refine.facility_key,
        facility_name=refine.facility_name,
        sell_price_basis=loaded.sell_price_basis,
        sell_markup=float(loaded.sell_markup),
    )
    lines = parse_eve_paste(paste)
    if not lines:
        return result

    resolved = resolve_types_by_name([line.name for line in lines])
    remaining = remaining_sale_quantities(exclude_order_id=exclude_order_id)
    lot_ids = set(remaining)
    for eve_type in resolved.values():
        if eve_type is not None:
            lot_ids.add(eve_type.id)
    lots = {
        eve_type.id: eve_type
        for eve_type in EveType.objects.filter(id__in=lot_ids).select_related(
            "eve_group", "eve_group__eve_category"
        )
    }

    picks: dict[int, FillPick] = {}
    remaining_minerals: dict[str, int] = {}
    unmatched: list[tuple[str, int, EveType | None]] = []

    for line in lines:
        eve_type = resolved.get(line.name)
        if eve_type is None:
            result.unresolved_names.append(line.name)
            unmatched.append((line.name, line.quantity, None))
            continue
        lots.setdefault(eve_type.id, eve_type)
        on_hand = remaining.get(eve_type.id, 0)
        take = min(on_hand, line.quantity)
        leftover = line.quantity - take
        if take > 0:
            remaining[eve_type.id] = on_hand - take
            _add_pick(
                picks,
                FillPick(
                    type_id=eve_type.id,
                    name=eve_type.name,
                    quantity=take,
                    fill_source="exact",
                    unit_price=None,
                    line_total=None,
                ),
            )
        if leftover <= 0:
            continue
        if eve_type.name in MINERAL_NAMES:
            remaining_minerals[eve_type.name] = (
                remaining_minerals.get(eve_type.name, 0) + leftover
            )
            continue
        classified = classify_eve_type(eve_type)
        if classified.category == BuybackCategory.ORE:
            yields = _ore_yields(
                eve_type.name, refine.rate_for_ore(eve_type.name)
            )
            for mineral, per_unit in yields.items():
                if mineral not in MINERAL_NAMES or per_unit <= 0:
                    continue
                remaining_minerals[mineral] = remaining_minerals.get(
                    mineral, 0
                ) + int(math.ceil(per_unit * leftover))
            continue
        unmatched.append((eve_type.name, leftover, eve_type))

    _allocate_ore_for_minerals(
        remaining, lots, remaining_minerals, refine, picks
    )

    for name, qty in remaining_minerals.items():
        if qty > 0:
            mineral_type = EveType.objects.filter(name=name).first()
            result.shortfalls.append(
                FillShortfall(
                    name=name,
                    quantity=qty,
                    type_id=mineral_type.id if mineral_type else None,
                )
            )
    for name, qty, eve_type in unmatched:
        if qty > 0:
            result.shortfalls.append(
                FillShortfall(
                    name=name,
                    quantity=qty,
                    type_id=eve_type.id if eve_type else None,
                )
            )

    priced = unit_prices_for_types(
        list(picks.keys()),
        settings=loaded,
    )
    ordered_picks: list[FillPick] = []
    priced_totals = []
    for pick in sorted(picks.values(), key=lambda row: row.name.lower()):
        unit = priced.get(pick.type_id)
        if unit is not None:
            pick.unit_price = float(unit)
            total = line_total(unit, pick.quantity)
            pick.line_total = float(total)
            priced_totals.append(total)
        ordered_picks.append(pick)
    result.picks = ordered_picks
    result.contract_total = contract_total_isk(priced_totals)
    result.janice_tsv = _tsv(
        [(pick.name, pick.quantity) for pick in ordered_picks]
    )
    result.shortfall_tsv = _tsv(
        [(row.name, row.quantity) for row in result.shortfalls]
    )
    result.unresolved_names = list(dict.fromkeys(result.unresolved_names))
    return result
