"""Economics helpers for admin LP store offer price tracking.

Conversion rates (isk/lp buy & sell) use baseline LocationPrice buy/sell when
present, else Forge history via get_prices_by_type_id. Alliance buyback
acquisition/profit columns remain separate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from django.db import ProgrammingError
from eveonline.models import EveLocation
from eveuniverse.models import EveType

from industry.helpers.blueprint_efficiency import is_faction_navy_hull
from industry.helpers.loyalty_store import resolve_isk_per_lp
from industry.helpers.product_unit_cost import (
    TALWAR_FI_BPC_TYPE_ID,
    TALWAR_FI_TYPE_ID,
    plan_product_unit_cost,
)
from industry.helpers.type_breakdown import get_blueprint_or_reaction_type_id
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLpStoreOffer,
    IndustryLpStoreOfferRequiredItem,
    IndustryProduct,
)
from market.helpers.pricing import (
    get_prices_by_type_id,
    get_volume_90d_by_type_id,
)
from market.models import EveMarketItemLocationPrice


@dataclass(frozen=True)
class LpStoreOfferEconomics:
    pk: int
    offer_id: int
    corporation_id: int
    type_id: int
    type_name: str
    currency_name: str
    isk_per_lp: Optional[float]
    lp_cost: int
    isk_cost: int
    ak_cost: int
    quantity: int
    required_items_summary: str
    other_cost: Optional[int]
    acquisition_isk_per_unit: Optional[int]
    market_type_id: int
    market_type_name: str
    jita_sell: Optional[int]
    jita_buy: Optional[int]
    conversion_isk_per_lp_sell: Optional[float]
    conversion_isk_per_lp_buy: Optional[float]
    volume_90d: Optional[int]
    build_cost_per_unit: Optional[int]
    cost_per_unit: Optional[int]
    kind: str
    profit_vs_sell: Optional[int]


def tracked_corporation_ids() -> List[int]:
    return list(
        IndustryLoyaltyPoint.objects.filter(is_active=True).values_list(
            "corporation_id", flat=True
        )
    )


def tracked_currencies_by_corporation_id() -> Dict[int, IndustryLoyaltyPoint]:
    return {
        int(row.corporation_id): row
        for row in IndustryLoyaltyPoint.objects.filter(is_active=True)
    }


def bpc_type_id_to_product_type_id() -> Dict[int, int]:
    mapping: Dict[int, int] = {TALWAR_FI_BPC_TYPE_ID: TALWAR_FI_TYPE_ID}
    products = IndustryProduct.objects.select_related(
        "eve_type", "eve_type__eve_group", "eve_type__eve_group__eve_category"
    ).filter(eve_type_id__isnull=False)
    for product in products:
        eve_type = product.eve_type
        if not is_faction_navy_hull(eve_type):
            continue
        bpc_id = get_blueprint_or_reaction_type_id(eve_type)
        if bpc_id is None:
            continue
        mapping[int(bpc_id)] = int(eve_type.id)
    return mapping


def _acquisition_isk_per_unit(
    offer: IndustryLpStoreOffer,
    isk_per_lp: Optional[float],
    other_cost: Optional[int],
) -> Optional[int]:
    if isk_per_lp is None or isk_per_lp <= 0:
        return None
    qty = max(offer.quantity, 1)
    extras = int(other_cost or 0)
    pack = int(
        round(offer.lp_cost * float(isk_per_lp) + offer.isk_cost + extras)
    )
    return int(round(pack / qty))


def _baseline_location_prices(
    type_ids: Iterable[int],
) -> Dict[int, Tuple[Optional[int], Optional[int]]]:
    """
    Return {type_id: (sell, buy)} from baseline EveLocation LocationPrice.
    Missing types omitted.
    """
    unique = list({int(t) for t in type_ids})
    if not unique:
        return {}
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    if baseline is None:
        return {}
    out: Dict[int, Tuple[Optional[int], Optional[int]]] = {}
    for row in EveMarketItemLocationPrice.objects.filter(
        location=baseline, item_id__in=unique
    ).values_list("item_id", "sell_price", "buy_price"):
        item_id, sell, buy = row
        out[int(item_id)] = (
            int(sell) if sell is not None else None,
            int(buy) if buy is not None else None,
        )
    return out


def _resolve_sell_buy(
    type_id: int,
    *,
    location_prices: Dict[int, Tuple[Optional[int], Optional[int]]],
    history_prices: Dict[int, int],
) -> Tuple[Optional[int], Optional[int]]:
    loc = location_prices.get(type_id)
    hist = history_prices.get(type_id)
    if loc is not None:
        sell = loc[0] if loc[0] is not None else hist
        buy = loc[1] if loc[1] is not None else hist
        return sell, buy
    return hist, hist


def _conversion_isk_per_lp(
    *,
    market_price: Optional[int],
    offer_qty: int,
    isk_cost: int,
    other_cost: Optional[int],
    lp_cost: int,
) -> Optional[float]:
    if market_price is None or lp_cost <= 0:
        return None
    extras = int(other_cost or 0)
    return (market_price * offer_qty - isk_cost - extras) / float(lp_cost)


def offer_economics_for_queryset(
    offers: Iterable[IndustryLpStoreOffer],
) -> Dict[int, LpStoreOfferEconomics]:
    """
    Economics keyed by IndustryLpStoreOffer.pk (stable unique identity).
    """
    rows = list(offers)
    if not rows:
        return {}

    # Prefetch required items when not already loaded.
    offer_ids = [o.pk for o in rows if o.pk is not None]
    req_by_offer: Dict[int, List[Tuple[int, int]]] = {
        pk: [] for pk in offer_ids
    }

    try:
        req_rows = list(
            IndustryLpStoreOfferRequiredItem.objects.filter(
                offer_id__in=offer_ids
            ).values_list("offer_id", "type_id", "quantity")
        )
    except ProgrammingError:
        # Migration for required-items table may not be applied yet.
        req_rows = []
    for offer_pk, type_id, qty in req_rows:
        req_by_offer.setdefault(int(offer_pk), []).append(
            (int(type_id), int(qty))
        )

    currencies = tracked_currencies_by_corporation_id()
    bpc_to_product = bpc_type_id_to_product_type_id()

    offer_type_ids = {o.type_id for o in rows}
    product_type_ids = {
        bpc_to_product[tid] for tid in offer_type_ids if tid in bpc_to_product
    }
    req_type_ids = {tid for items in req_by_offer.values() for tid, _ in items}
    market_type_ids = sorted(offer_type_ids | product_type_ids | req_type_ids)
    history_prices = get_prices_by_type_id(market_type_ids)
    location_prices = _baseline_location_prices(market_type_ids)
    volumes = get_volume_90d_by_type_id(market_type_ids)
    type_names = {
        tid: (name or str(tid))
        for tid, name in EveType.objects.filter(
            id__in=market_type_ids
        ).values_list("id", "name")
    }

    build_costs: Dict[int, int] = {}
    for product_type_id in sorted(product_type_ids):
        try:
            unit = plan_product_unit_cost(
                product_type_id, use_production_lp=True
            )
        except ValueError:
            continue
        build_costs[product_type_id] = unit.cost_per

    out: Dict[int, LpStoreOfferEconomics] = {}
    for offer in rows:
        corp_id = offer.corporation_id
        type_id = offer.type_id
        currency = currencies.get(corp_id)
        currency_name = currency.name if currency is not None else str(corp_id)
        isk_per_lp = resolve_isk_per_lp(requested=None, corporation_id=corp_id)

        required = req_by_offer.get(int(offer.pk), []) if offer.pk else []
        other_cost: Optional[int] = 0 if not required else None
        req_parts: List[str] = []
        if required:
            total = 0
            priced = True
            for req_type_id, req_qty in required:
                sell, _ = _resolve_sell_buy(
                    req_type_id,
                    location_prices=location_prices,
                    history_prices=history_prices,
                )
                name = type_names.get(req_type_id, str(req_type_id))
                req_parts.append(f"{name} x{req_qty}")
                if sell is None:
                    priced = False
                else:
                    total += sell * req_qty
            other_cost = total if priced else None

        acquisition = _acquisition_isk_per_unit(offer, isk_per_lp, other_cost)

        product_type_id = bpc_to_product.get(type_id)
        if product_type_id is not None:
            kind = "blueprint"
            market_type_id = product_type_id
            build_cost = build_costs.get(product_type_id)
            cost_per_unit = build_cost
        else:
            kind = "input"
            market_type_id = type_id
            build_cost = None
            cost_per_unit = acquisition

        jita_sell, jita_buy = _resolve_sell_buy(
            market_type_id,
            location_prices=location_prices,
            history_prices=history_prices,
        )
        profit = (
            jita_sell - cost_per_unit
            if jita_sell is not None and cost_per_unit is not None
            else None
        )
        conv_sell = _conversion_isk_per_lp(
            market_price=jita_sell,
            offer_qty=max(offer.quantity, 1),
            isk_cost=offer.isk_cost,
            other_cost=other_cost,
            lp_cost=offer.lp_cost,
        )
        conv_buy = _conversion_isk_per_lp(
            market_price=jita_buy,
            offer_qty=max(offer.quantity, 1),
            isk_cost=offer.isk_cost,
            other_cost=other_cost,
            lp_cost=offer.lp_cost,
        )

        out[offer.pk] = LpStoreOfferEconomics(
            pk=offer.pk,
            offer_id=offer.offer_id,
            corporation_id=corp_id,
            type_id=type_id,
            type_name=type_names.get(type_id, str(type_id)),
            currency_name=currency_name,
            isk_per_lp=isk_per_lp,
            lp_cost=offer.lp_cost,
            isk_cost=offer.isk_cost,
            ak_cost=int(offer.ak_cost or 0),
            quantity=offer.quantity,
            required_items_summary=", ".join(req_parts) if req_parts else "",
            other_cost=other_cost,
            acquisition_isk_per_unit=acquisition,
            market_type_id=market_type_id,
            market_type_name=type_names.get(
                market_type_id, str(market_type_id)
            ),
            jita_sell=jita_sell,
            jita_buy=jita_buy,
            conversion_isk_per_lp_sell=conv_sell,
            conversion_isk_per_lp_buy=conv_buy,
            volume_90d=volumes.get(market_type_id),
            build_cost_per_unit=build_cost,
            cost_per_unit=cost_per_unit,
            kind=kind,
            profit_vs_sell=profit,
        )
    return out
