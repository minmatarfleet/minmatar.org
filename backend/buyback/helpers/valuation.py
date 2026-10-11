"""Estimate market-guide ISK values for buyback stock / ledger display."""

from __future__ import annotations

from typing import Sequence

from eveuniverse.models import EveType

from buyback.helpers.accepted_items import (
    compressed_ore_buy_market_name,
    ore_jita_buy_unit,
)
from buyback.helpers.classify import BuybackCategory, classify_eve_type
from buyback.helpers.demand import mineral_name_to_id_for_ores
from buyback.helpers.pricing import (
    get_baseline_buy_prices,
    get_baseline_buy_prices_by_name,
    price_flat_line,
    price_ore_line,
)
from buyback.models import EveBuybackSettings


def batch_estimate_guide_isk(
    rows: Sequence[tuple[int | None, str, int]],
) -> list[float | None]:
    """Market-guide line totals (Jita baseline) parallel to rows.

    Each row is (type_id, name, quantity). Ore uses min(base Jita buy,
    refined minerals) at the configured refine rate; other types use
    Jita buy × qty.
    """
    if not rows:
        return []

    settings = EveBuybackSettings.load()
    rules = settings.rates()
    refine_rate = float(rules["ore_refine"])

    type_ids = [int(type_id) for type_id, _, _ in rows if type_id]
    types_by_id = {
        eve_type.id: eve_type
        for eve_type in EveType.objects.filter(id__in=type_ids)
    }

    ore_names: list[str] = []
    flat_type_ids: list[int] = []
    categories: list[BuybackCategory | None] = []
    for type_id, name, quantity in rows:
        eve_type = types_by_id.get(int(type_id)) if type_id else None
        if eve_type is None and name:
            eve_type = EveType.objects.filter(name=name).first()
        if eve_type is None:
            categories.append(None)
            continue
        classified = classify_eve_type(eve_type)
        categories.append(classified.category)
        if classified.category == BuybackCategory.ORE:
            ore_names.append(eve_type.name)
        elif type_id:
            flat_type_ids.append(int(type_id))
        else:
            flat_type_ids.append(eve_type.id)

    mineral_name_to_id = mineral_name_to_id_for_ores(ore_names)
    ore_market_names = [
        name
        for name in (compressed_ore_buy_market_name(n) for n in ore_names)
        if name
    ]
    buy_by_name = get_baseline_buy_prices_by_name(
        list(mineral_name_to_id.keys()) + ore_market_names
    )
    buy_by_id = get_baseline_buy_prices(list(set(flat_type_ids)))

    totals: list[float | None] = []
    for (type_id, name, quantity), category in zip(rows, categories):
        if quantity <= 0 or category is None:
            totals.append(None)
            continue
        resolved_id = int(type_id) if type_id else None
        eve_type = types_by_id.get(resolved_id) if resolved_id else None
        display_name = eve_type.name if eve_type is not None else name

        if category == BuybackCategory.ORE:
            priced = price_ore_line(
                name=display_name,
                quantity=int(quantity),
                type_id=resolved_id,
                refine_rate=refine_rate,
                jita_share=1.0,
                mineral_buy_by_name=buy_by_name,
                ore_unit_buy=ore_jita_buy_unit(display_name, buy_by_name),
            )
        elif category in (BuybackCategory.EXCLUDED, BuybackCategory.UNKNOWN):
            totals.append(None)
            continue
        else:
            buy = buy_by_id.get(resolved_id) if resolved_id else None
            priced = price_flat_line(
                name=display_name,
                quantity=int(quantity),
                type_id=resolved_id,
                category=category,
                rate=1.0,
                buy_price=buy,
            )
        totals.append(priced.line_total)
    return totals
