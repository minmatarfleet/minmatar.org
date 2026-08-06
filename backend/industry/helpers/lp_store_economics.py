"""Economics helpers for LP store offer price tracking.

Conversion rates (isk/lp buy & sell) follow Fuzzwork's LP store formula:
  (market_price * qty - isk_cost - other_cost) / lp_cost
where other_cost is LP-store required items plus, for blueprints, Amamake
build-planner manufacturing cost × offer quantity (compressed ore, job
install, facility/SCC/reprocessing taxes, freight — excluding navy BPC
LP/ISK, which stay in the formula via lp_cost / isk_cost). Market prices
use baseline LocationPrice buy/sell when present, else Forge history via
get_prices_by_type_id.

Acquisition (LP×buyback rate + ISK + LP required items only) stays separate
from conversion — it is the LP-desk cost, not finished-hull build cost.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, Iterable, List, Optional, Set, Tuple

from django.db import ProgrammingError
from django.db.models import Sum
from django.utils import timezone
from eveonline.models import EveLocation
from eveuniverse.models import EveType

from industry.helpers.blueprint_efficiency import is_faction_navy_hull
from industry.helpers.lp_catalog import ensure_eve_types
from industry.helpers.loyalty_store import resolve_isk_per_lp
from industry.helpers.product_unit_cost import (
    TALWAR_FI_BPC_TYPE_ID,
    TALWAR_FI_TYPE_ID,
    plan_product_unit_cost,
)
from industry.helpers.type_breakdown import (
    get_blueprint_or_reaction_type_id,
)
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLpStoreOffer,
    IndustryLpStoreOfferRequiredItem,
    IndustryProduct,
)
from market.helpers.pricing import (
    VOLUME_WINDOWS,
    _baseline_region_id,
    get_prices_by_type_id,
    get_volume_weighted_average_by_type_id,
    get_volume_windows_by_type_id,
)
from market.models import EveMarketItemLocationPrice
from market.models.history import EveMarketItemHistory

# Forge 30d traded units below this (or missing history) = negligible LP
# liquidity. Fuzzwork's "5% Volume" is order-book depth (qty within 5% of
# best price); we only store LocationPrice bests, so 30d history volume is
# the pragmatic viability proxy. Threshold 1 keeps thin ship markets
# (1–5 hulls/month) while dropping truly dead / unsynced types.
NEGLIGIBLE_LP_FORGE_VOLUME_30D = 1


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
    jita_avg_7d: Optional[int]
    conversion_isk_per_lp_sell: Optional[float]
    conversion_isk_per_lp_buy: Optional[float]
    conversion_isk_per_lp_avg_7d: Optional[float]
    volume_1d: Optional[int]
    volume_7d: Optional[int]
    volume_30d: Optional[int]
    build_cost_per_unit: Optional[int]
    cost_per_unit: Optional[int]
    kind: str
    profit_vs_sell: Optional[int]


def display_type_name(econ: LpStoreOfferEconomics) -> str:
    """Public display name, including (BPC) for blueprint copies."""
    if econ.kind == "blueprint" and econ.market_type_id != econ.type_id:
        return f"{econ.market_type_name} (BPC)"
    return econ.type_name


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


def market_type_ids_with_viable_forge_volume(
    type_ids: Optional[Iterable[int]] = None,
    *,
    min_volume_30d: int = NEGLIGIBLE_LP_FORGE_VOLUME_30D,
) -> Set[int]:
    """
    Market type IDs with Forge 30d history volume >= ``min_volume_30d``.

    Types with no recent history rows are omitted (treated as negligible by
    callers). Requires EveMarketItemHistory sync for LP catalog types.
    When ``type_ids`` is given, only those IDs are considered.
    """
    region_id = _baseline_region_id()
    cutoff = timezone.now().date() - timedelta(days=30)
    qs = EveMarketItemHistory.objects.filter(
        region_id=region_id,
        date__gte=cutoff,
    )
    if type_ids is not None:
        unique = {int(t) for t in type_ids if int(t) > 0}
        if not unique:
            return set()
        qs = qs.filter(item_id__in=unique)
    rows = (
        qs.values("item_id")
        .annotate(total=Sum("volume"))
        .filter(total__gte=int(min_volume_30d))
        .values_list("item_id", flat=True)
    )
    return {int(item_id) for item_id in rows}


def offer_type_ids_with_viable_forge_volume(
    offer_type_ids: Iterable[int],
    *,
    min_volume_30d: int = NEGLIGIBLE_LP_FORGE_VOLUME_30D,
    bpc_to_hull: Optional[Dict[int, int]] = None,
) -> Set[int]:
    """
    Offer ``type_id``s whose market type (hull for navy BPCs) clears the
    30d Forge volume floor. Missing history → not viable.
    """
    unique = {int(t) for t in offer_type_ids if int(t) > 0}
    if not unique:
        return set()
    mapping = (
        bpc_to_hull
        if bpc_to_hull is not None
        else bpc_type_id_to_product_type_id()
    )
    market_ids = {mapping.get(tid, tid) for tid in unique}
    viable_market = market_type_ids_with_viable_forge_volume(
        market_ids,
        min_volume_30d=min_volume_30d,
    )
    return {tid for tid in unique if mapping.get(tid, tid) in viable_market}


def offer_is_below_set_lp_price(
    econ: LpStoreOfferEconomics, *, side: str = "sell"
) -> bool:
    """
    True when ISK/LP conversion is worse than the currency's set buyback.

    Compares sell, buy, or 7d average conversion (per ``side``) to
    ``default_isk_per_lp`` (``econ.isk_per_lp``). Null conversion or
    missing set price counts as below set. Exact equality counts as
    at/above the set price.
    """
    if side == "buy":
        rate = econ.conversion_isk_per_lp_buy
    elif side == "avg_7d":
        rate = econ.conversion_isk_per_lp_avg_7d
    else:
        rate = econ.conversion_isk_per_lp_sell
    if rate is None:
        return True
    buyback = econ.isk_per_lp
    if buyback is None:
        return True
    return float(rate) < float(buyback)


def offer_pks_below_set_lp_price(
    offers: Iterable[IndustryLpStoreOffer],
    *,
    economics: Optional[Dict[int, LpStoreOfferEconomics]] = None,
    side: str = "sell",
) -> Set[int]:
    """Primary keys of offers below the currency's set LP buy price.

    Pass a precomputed ``economics`` map (e.g. request-scoped catalog cache)
    to avoid recomputing offer_economics_for_queryset per filter.
    """
    rows = list(offers)
    if not rows:
        return set()
    if economics is None:
        economics = offer_economics_for_queryset(rows)
    below: Set[int] = set()
    for offer in rows:
        pk = offer.pk
        if pk is None:
            continue
        row = economics.get(pk)
        if row is None or offer_is_below_set_lp_price(row, side=side):
            below.add(pk)
    return below


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


def _lp_store_required_cost(
    required: List[Tuple[int, int]],
    *,
    location_prices: Dict[int, Tuple[Optional[int], Optional[int]]],
    history_prices: Dict[int, int],
    type_names: Dict[int, str],
) -> Tuple[Optional[int], List[str]]:
    """Return (LP-desk other cost, summary parts) for required items."""
    if not required:
        return 0, []
    total = 0
    priced = True
    parts: List[str] = []
    for req_type_id, req_qty in required:
        sell, _ = _resolve_sell_buy(
            req_type_id,
            location_prices=location_prices,
            history_prices=history_prices,
        )
        name = type_names.get(req_type_id, str(req_type_id))
        parts.append(f"{name} x{req_qty}")
        if sell is None:
            priced = False
        else:
            total += sell * req_qty
    return (total if priced else None), parts


def _combine_other_cost(
    lp_store_other: Optional[int],
    build_other: Optional[int],
) -> Optional[int]:
    if lp_store_other is None or build_other is None:
        return None
    return int(lp_store_other) + int(build_other)


def _amamake_manufacturing_costs(
    product_type_ids: Iterable[int],
    batch_sizes: Iterable[int],
) -> Tuple[Dict[int, int], Dict[Tuple[int, int], Optional[int]]]:
    """
    Amamake planner costs for navy hulls.

    Returns:
      build_cost_per_unit: full unit cost at qty=1 (includes navy BPC LP)
      mfg_cost_per: manufacturing-only unit cost keyed by (product, batch)
    """
    products = sorted({int(t) for t in product_type_ids})
    batches = sorted({max(int(q), 1) for q in batch_sizes})
    build_cost_per_unit: Dict[int, int] = {}
    mfg_cost_per: Dict[Tuple[int, int], Optional[int]] = {}
    if not products:
        return build_cost_per_unit, mfg_cost_per

    for product_type_id in products:
        try:
            unit = plan_product_unit_cost(
                product_type_id, quantity=1, use_production_lp=True
            )
        except ValueError:
            continue
        build_cost_per_unit[product_type_id] = unit.cost_per
        mfg_cost_per[(product_type_id, 1)] = unit.manufacturing_cost_per

    for product_type_id in products:
        for batch in batches:
            if batch == 1:
                continue
            try:
                unit = plan_product_unit_cost(
                    product_type_id,
                    quantity=batch,
                    use_production_lp=True,
                )
            except ValueError:
                mfg_cost_per[(product_type_id, batch)] = None
                continue
            mfg_cost_per[(product_type_id, batch)] = (
                unit.manufacturing_cost_per
            )

    return build_cost_per_unit, mfg_cost_per


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
    blueprint_batch_sizes = {
        max(o.quantity, 1) for o in rows if o.type_id in bpc_to_product
    }
    req_type_ids = {tid for items in req_by_offer.values() for tid, _ in items}
    market_type_ids = sorted(offer_type_ids | product_type_ids | req_type_ids)
    ensure_eve_types(market_type_ids)
    history_prices = get_prices_by_type_id(market_type_ids)
    avg_7d_prices = get_volume_weighted_average_by_type_id(
        market_type_ids, days=7
    )
    location_prices = _baseline_location_prices(market_type_ids)
    volume_windows = get_volume_windows_by_type_id(
        market_type_ids, windows=VOLUME_WINDOWS
    )
    type_names = {
        tid: (name or str(tid))
        for tid, name in EveType.objects.filter(
            id__in=market_type_ids
        ).values_list("id", "name")
    }

    build_costs, mfg_cost_per = _amamake_manufacturing_costs(
        product_type_ids, blueprint_batch_sizes
    )

    out: Dict[int, LpStoreOfferEconomics] = {}
    for offer in rows:
        corp_id = offer.corporation_id
        type_id = offer.type_id
        currency = currencies.get(corp_id)
        currency_name = currency.name if currency is not None else str(corp_id)
        isk_per_lp = resolve_isk_per_lp(requested=None, corporation_id=corp_id)

        required = req_by_offer.get(int(offer.pk), []) if offer.pk else []
        lp_store_other, req_parts = _lp_store_required_cost(
            required,
            location_prices=location_prices,
            history_prices=history_prices,
            type_names=type_names,
        )

        runs = max(offer.quantity, 1)
        product_type_id = bpc_to_product.get(type_id)
        if product_type_id is not None:
            kind = "blueprint"
            market_type_id = product_type_id
            build_cost = build_costs.get(product_type_id)
            # Amamake manufacturing (excl. navy BPC LP) × offer quantity.
            # BPC LP/ISK remain in the conversion formula via lp_cost/isk_cost.
            mfg_per = mfg_cost_per.get((product_type_id, runs))
            build_other = None if mfg_per is None else int(mfg_per) * runs
        else:
            kind = "input"
            market_type_id = type_id
            build_cost = None
            build_other = 0

        other_cost = _combine_other_cost(lp_store_other, build_other)

        acquisition = _acquisition_isk_per_unit(
            offer, isk_per_lp, lp_store_other
        )

        # Cost/Profit compare LP-store acquisition per unit, not planner
        # build cost (identical across same-hull BPCs) and not Amamake mfg.
        cost_per_unit = acquisition

        jita_sell, jita_buy = _resolve_sell_buy(
            market_type_id,
            location_prices=location_prices,
            history_prices=history_prices,
        )
        jita_avg_7d = avg_7d_prices.get(market_type_id)
        profit = (
            jita_sell - cost_per_unit
            if jita_sell is not None and cost_per_unit is not None
            else None
        )
        conv_sell = _conversion_isk_per_lp(
            market_price=jita_sell,
            offer_qty=runs,
            isk_cost=offer.isk_cost,
            other_cost=other_cost,
            lp_cost=offer.lp_cost,
        )
        conv_buy = _conversion_isk_per_lp(
            market_price=jita_buy,
            offer_qty=runs,
            isk_cost=offer.isk_cost,
            other_cost=other_cost,
            lp_cost=offer.lp_cost,
        )
        conv_avg_7d = _conversion_isk_per_lp(
            market_price=jita_avg_7d,
            offer_qty=runs,
            isk_cost=offer.isk_cost,
            other_cost=other_cost,
            lp_cost=offer.lp_cost,
        )
        vols = volume_windows.get(market_type_id) or {}

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
            jita_avg_7d=jita_avg_7d,
            conversion_isk_per_lp_sell=conv_sell,
            conversion_isk_per_lp_buy=conv_buy,
            conversion_isk_per_lp_avg_7d=conv_avg_7d,
            volume_1d=vols.get(1),
            volume_7d=vols.get(7),
            volume_30d=vols.get(30),
            build_cost_per_unit=build_cost,
            cost_per_unit=cost_per_unit,
            kind=kind,
            profit_vs_sell=profit,
        )
    return out
