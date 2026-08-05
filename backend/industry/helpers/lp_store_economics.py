"""Economics helpers for admin LP store offer price tracking.

Conversion rates (isk/lp buy & sell) follow Fuzzwork's LP store formula:
  (market_price * qty - isk_cost - other_cost) / lp_cost
where other_cost is LP-store required items plus, for blueprints, SDE
manufacturing materials × offer quantity (Fuzzwork "Materials to build" at
PE5 / ME0). Market prices use baseline LocationPrice buy/sell when present,
else Forge history via get_prices_by_type_id.

Acquisition (LP×buyback rate + ISK + LP required items only) stays separate
from conversion — it is the LP-desk cost, not finished-hull build cost.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, Iterable, List, Optional, Set, Tuple

from django.db import ProgrammingError
from django.db.models import (
    ExpressionWrapper,
    F,
    FloatField,
    OuterRef,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone
from eveonline.models import EveLocation
from eveuniverse.models import EveIndustryActivityMaterial, EveType

from industry.helpers.blueprint_efficiency import is_faction_navy_hull
from industry.helpers.lp_catalog import ensure_eve_types
from industry.helpers.loyalty_store import resolve_isk_per_lp
from industry.helpers.product_unit_cost import (
    TALWAR_FI_BPC_TYPE_ID,
    TALWAR_FI_TYPE_ID,
    plan_product_unit_cost,
)
from industry.helpers.type_breakdown import (
    ACTIVITY_MANUFACTURING,
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
    conversion_isk_per_lp_sell: Optional[float]
    conversion_isk_per_lp_buy: Optional[float]
    volume_1d: Optional[int]
    volume_7d: Optional[int]
    volume_30d: Optional[int]
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


def offer_is_below_set_lp_price(econ: LpStoreOfferEconomics) -> bool:
    """
    True when ISK/LP sell conversion is worse than alliance buyback.

    Below-set means ``conversion_isk_per_lp_sell`` is null or strictly
    less than the currency's ``default_isk_per_lp`` (``econ.isk_per_lp``).
    Exact equality counts as at/above the set buy price.
    """
    rate = econ.conversion_isk_per_lp_sell
    if rate is None:
        return True
    buyback = econ.isk_per_lp
    if buyback is None:
        return True
    return float(rate) < float(buyback)


def offer_pks_below_set_lp_price(
    offers: Iterable[IndustryLpStoreOffer],
) -> Set[int]:
    """Primary keys of offers below the currency's set LP buy price."""
    rows = list(offers)
    if not rows:
        return set()
    economics = offer_economics_for_queryset(rows)
    below: Set[int] = set()
    for offer in rows:
        pk = offer.pk
        if pk is None:
            continue
        row = economics.get(pk)
        if row is None or offer_is_below_set_lp_price(row):
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


def manufacturing_materials_by_blueprint_type_id(
    type_ids: Iterable[int],
) -> Dict[int, List[Tuple[int, int]]]:
    """
    SDE manufacturing bill of materials keyed by blueprint type_id.

    Quantities are ME0 / max Production Efficiency (Fuzzwork PE5) base runs.
    Blueprints with no manufacturing rows are omitted.
    """
    unique = list({int(t) for t in type_ids})
    if not unique:
        return {}
    out: Dict[int, List[Tuple[int, int]]] = {}
    for bpc_id, mat_id, qty in EveIndustryActivityMaterial.objects.filter(
        eve_type_id__in=unique,
        activity_id=ACTIVITY_MANUFACTURING,
    ).values_list("eve_type_id", "material_eve_type_id", "quantity"):
        out.setdefault(int(bpc_id), []).append((int(mat_id), int(qty)))
    return out


def _priced_material_pack_cost(
    materials: List[Tuple[int, int]],
    *,
    runs: int,
    location_prices: Dict[int, Tuple[Optional[int], Optional[int]]],
    history_prices: Dict[int, int],
) -> Optional[int]:
    """Sum sell×qty×runs for a BOM; None if any material lacks a price."""
    if not materials:
        return 0
    total = 0
    for mat_type_id, mat_qty in materials:
        sell, _ = _resolve_sell_buy(
            mat_type_id,
            location_prices=location_prices,
            history_prices=history_prices,
        )
        if sell is None:
            return None
        total += sell * mat_qty * runs
    return total


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


def _fuzzwork_other_cost(
    lp_store_other: Optional[int],
    build_mats_other: Optional[int],
) -> Optional[int]:
    if lp_store_other is None or build_mats_other is None:
        return None
    return int(lp_store_other) + int(build_mats_other)


def annotate_lp_store_offer_sort_fields(queryset):
    """
    Annotate admin sort keys for economics columns.

    Display values still come from offer_economics_for_queryset (accurate
    hull mapping, required-item other cost). Sort annotations use offer
    type_id history + currency default ISK/LP and ignore required-item
    other cost — good enough for Fuzzwork-style ranking.
    """
    region_id = _baseline_region_id()
    today = timezone.now().date()

    type_name_sq = EveType.objects.filter(id=OuterRef("type_id")).values(
        "name"
    )[:1]
    hist_avg_sq = (
        EveMarketItemHistory.objects.filter(
            region_id=region_id,
            item_id=OuterRef("type_id"),
        )
        .order_by("-date")
        .values("average")[:1]
    )
    currency_ipl_sq = IndustryLoyaltyPoint.objects.filter(
        corporation_id=OuterRef("corporation_id"),
        is_active=True,
    ).values("default_isk_per_lp")[:1]

    def _volume_sq(days: int):
        cutoff = today - timedelta(days=days)
        return (
            EveMarketItemHistory.objects.filter(
                region_id=region_id,
                item_id=OuterRef("type_id"),
                date__gte=cutoff,
            )
            .values("item_id")
            .annotate(total=Sum("volume"))
            .values("total")[:1]
        )

    qs = queryset.annotate(
        sort_type_name=Subquery(type_name_sq),
        sort_jita_price=Subquery(hist_avg_sq),
        sort_volume_1d=Subquery(_volume_sq(1)),
        sort_volume_7d=Subquery(_volume_sq(7)),
        sort_volume_30d=Subquery(_volume_sq(30)),
        sort_isk_per_lp=Subquery(currency_ipl_sq),
    )
    # Acquisition / conversion / profit approximations without other_cost.
    qs = qs.annotate(
        sort_acquisition=ExpressionWrapper(
            (
                F("lp_cost") * Coalesce(F("sort_isk_per_lp"), Value(0.0))
                + F("isk_cost")
            )
            / Greatest(F("quantity"), Value(1)),
            output_field=FloatField(),
        ),
        sort_conversion_sell=ExpressionWrapper(
            (
                Coalesce(F("sort_jita_price"), Value(0.0)) * F("quantity")
                - F("isk_cost")
            )
            / Greatest(F("lp_cost"), Value(1)),
            output_field=FloatField(),
        ),
        sort_conversion_buy=ExpressionWrapper(
            (
                Coalesce(F("sort_jita_price"), Value(0.0)) * F("quantity")
                - F("isk_cost")
            )
            / Greatest(F("lp_cost"), Value(1)),
            output_field=FloatField(),
        ),
        sort_profit=ExpressionWrapper(
            Coalesce(F("sort_jita_price"), Value(0.0))
            - (
                (
                    F("lp_cost") * Coalesce(F("sort_isk_per_lp"), Value(0.0))
                    + F("isk_cost")
                )
                / Greatest(F("quantity"), Value(1))
            ),
            output_field=FloatField(),
        ),
    )
    return qs


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
    bom_by_bpc = manufacturing_materials_by_blueprint_type_id(offer_type_ids)
    bom_type_ids = {
        mat_id for mats in bom_by_bpc.values() for mat_id, _ in mats
    }
    market_type_ids = sorted(
        offer_type_ids | product_type_ids | req_type_ids | bom_type_ids
    )
    ensure_eve_types(market_type_ids)
    history_prices = get_prices_by_type_id(market_type_ids)
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
        lp_store_other, req_parts = _lp_store_required_cost(
            required,
            location_prices=location_prices,
            history_prices=history_prices,
            type_names=type_names,
        )

        # Fuzzwork: Other Cost = LP required items + materials to build
        # (manufacturing BOM × offer quantity). Acquisition stays LP-desk only.
        runs = max(offer.quantity, 1)
        build_mats_other = _priced_material_pack_cost(
            bom_by_bpc.get(type_id, []),
            runs=runs,
            location_prices=location_prices,
            history_prices=history_prices,
        )
        other_cost = _fuzzwork_other_cost(lp_store_other, build_mats_other)

        acquisition = _acquisition_isk_per_unit(
            offer, isk_per_lp, lp_store_other
        )

        product_type_id = bpc_to_product.get(type_id)
        if product_type_id is not None:
            kind = "blueprint"
            market_type_id = product_type_id
            build_cost = build_costs.get(product_type_id)
        else:
            kind = "input"
            market_type_id = type_id
            build_cost = None

        # Cost/Profit compare LP-store acquisition per unit, not planner
        # build cost (identical across same-hull BPCs) and not BOM other cost.
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
            conversion_isk_per_lp_sell=conv_sell,
            conversion_isk_per_lp_buy=conv_buy,
            volume_1d=vols.get(1),
            volume_7d=vols.get(7),
            volume_30d=vols.get(30),
            build_cost_per_unit=build_cost,
            cost_per_unit=cost_per_unit,
            kind=kind,
            profit_vs_sell=profit,
        )
    return out
