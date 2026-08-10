"""Orchestrate buyback paste → classify → price against Jita buy."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from buyback.helpers.accepted_items import get_active_accepted_type_ids
from buyback.helpers.classify import (
    BuybackCategory,
    classify_eve_type,
    resolve_types_by_name,
)
from buyback.helpers.demand import (
    mineral_name_to_id_for_ores,
    rate_reason_for_in_demand,
    stored_demand_by_type_id,
)
from buyback.helpers.paste import PasteLine, parse_eve_paste
from buyback.helpers.pricing import (
    PricedLine,
    get_baseline_buy_prices,
    get_baseline_buy_prices_by_name,
    price_flat_line,
    price_ore_line,
)
from buyback.models import EveBuybackSettings


@dataclass
class AppraisalResult:
    lines: list[PricedLine]
    offer_total: float
    accepted_count: int
    rejected_count: int
    rate_rules: dict[str, float]


def _jita_rate_for_demand(in_demand: bool, rules: dict[str, float]) -> float:
    if in_demand:
        return float(rules["demand_jita_buy"])
    return float(rules["surplus_jita_buy"])


def appraise_paste(
    paste: str,
    *,
    settings: EveBuybackSettings | None = None,
) -> AppraisalResult:
    """Appraise an EVE paste with buyback rate rules and baseline Jita buy."""
    buyback_settings = settings or EveBuybackSettings.load()
    rules = buyback_settings.rates()

    paste_lines: list[PasteLine] = parse_eve_paste(paste)
    if not paste_lines:
        return AppraisalResult(
            lines=[],
            offer_total=0.0,
            accepted_count=0,
            rejected_count=0,
            rate_rules=rules,
        )

    names = [line.name for line in paste_lines]
    types_by_name = resolve_types_by_name(names)
    accepted_type_ids = get_active_accepted_type_ids()
    demand_by_type_id = stored_demand_by_type_id()

    type_ids = [t.id for t in types_by_name.values() if t is not None]
    buy_by_id = get_baseline_buy_prices(type_ids)

    ore_names = []
    for line in paste_lines:
        eve_type = types_by_name.get(line.name)
        if eve_type is None or eve_type.id not in accepted_type_ids:
            continue
        if classify_eve_type(eve_type).category == BuybackCategory.ORE:
            ore_names.append(line.name)

    mineral_name_to_id = mineral_name_to_id_for_ores(ore_names)
    mineral_buy_by_name = get_baseline_buy_prices_by_name(
        list(mineral_name_to_id.keys())
    )

    priced: list[PricedLine] = []
    for line in paste_lines:
        eve_type = types_by_name.get(line.name)
        if eve_type is None:
            priced.append(
                PricedLine(
                    type_id=None,
                    name=line.name,
                    quantity=line.quantity,
                    category=BuybackCategory.UNKNOWN.value,
                    rate=None,
                    unit_price=None,
                    line_total=None,
                    accepted=False,
                    reject_reason="Unknown item name",
                )
            )
            continue

        if eve_type.id not in accepted_type_ids:
            priced.append(
                PricedLine(
                    type_id=eve_type.id,
                    name=eve_type.name,
                    quantity=line.quantity,
                    category=BuybackCategory.UNKNOWN.value,
                    rate=None,
                    unit_price=None,
                    line_total=None,
                    accepted=False,
                    reject_reason="Item type is not accepted for buyback",
                )
            )
            continue

        classification = classify_eve_type(eve_type)
        if classification.category in (
            BuybackCategory.EXCLUDED,
            BuybackCategory.UNKNOWN,
        ):
            priced.append(
                PricedLine(
                    type_id=eve_type.id,
                    name=eve_type.name,
                    quantity=line.quantity,
                    category=classification.category.value,
                    rate=None,
                    unit_price=None,
                    line_total=None,
                    accepted=False,
                    reject_reason=classification.reject_reason
                    or "Not accepted",
                )
            )
            continue

        in_demand = bool(demand_by_type_id.get(eve_type.id, False))
        rate = _jita_rate_for_demand(in_demand, rules)
        rate_reason = rate_reason_for_in_demand(in_demand)

        if classification.category == BuybackCategory.ORE:
            priced.append(
                price_ore_line(
                    name=eve_type.name,
                    quantity=line.quantity,
                    type_id=eve_type.id,
                    refine_rate=float(rules["ore_refine"]),
                    jita_share=rate,
                    mineral_buy_by_name=mineral_buy_by_name,
                    rate_reason=rate_reason,
                )
            )
            continue

        buy_price: Decimal | None = buy_by_id.get(eve_type.id)
        priced.append(
            price_flat_line(
                name=eve_type.name,
                quantity=line.quantity,
                type_id=eve_type.id,
                category=classification.category,
                rate=rate,
                buy_price=buy_price,
                rate_reason=rate_reason,
            )
        )

    accepted = [line for line in priced if line.accepted]
    rejected = [line for line in priced if not line.accepted]
    offer_total = round(sum(line.line_total or 0.0 for line in accepted), 2)

    return AppraisalResult(
        lines=priced,
        offer_total=offer_total,
        accepted_count=len(accepted),
        rejected_count=len(rejected),
        rate_rules=rules,
    )
