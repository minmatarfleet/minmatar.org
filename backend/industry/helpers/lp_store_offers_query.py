"""Shared LP store offer filtering, search, sort, and economics cache.

Used by admin changelist and the public loyalty offers API so filter
semantics stay single-sourced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from django.core.cache import cache
from django.db.models import (
    Case,
    Count,
    F,
    IntegerField,
    Max,
    Q,
    QuerySet,
    When,
)
from eveuniverse.models import EveType
from market.models.history import EveMarketItemHistory

from industry.helpers.lp_catalog import (
    chip_type_ids,
    skin_type_ids,
    supply_package_type_ids,
    tag_type_ids,
)
from industry.helpers.lp_store_economics import (
    LpStoreOfferEconomics,
    annotate_lp_store_offer_sort_fields,
    offer_economics_for_queryset,
    offer_is_below_set_lp_price,
    tracked_corporation_ids,
)
from industry.helpers.lp_store_useless import (
    offer_is_useless,
    peer_stats_by_corporation,
)
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLpStoreOffer,
    IndustryLpStoreOfferEconomics,
    IndustryLpStoreOfferRequiredItem,
)

# Request attribute for one shared tracked-catalog economics map per
# request (filters + list_display stash). Avoids N× full recomputes.
LP_OFFER_ECON_ATTR = "_lp_offer_econ"
# Short-lived cross-request cache so toggling filters does not recompute
# ~1.5k offers every time. Invalidates when offer/currency/history inputs
# change; TTL bounds LocationPrice / planner staleness.
_LP_OFFER_ECON_CACHE_PREFIX = "industry:lp_offer_econ:v1"
_LP_OFFER_ECON_CACHE_TTL = 180
LP_ECON_FILTER_PARAMS = (
    "exclude_useless_offers",
    "exclude_below_set_lp_price",
)

# Admin annotation names → LpStoreOfferEconomics attributes.
# Approximate SQL annotations ignore other_cost/BOM/hull mapping; when these
# keys appear in ordering we re-sort from request economics so the UI matches
# displayed ISK/LP and volume columns.
LP_OFFER_ECON_ORDER_ATTR = {
    "sort_conversion_sell": "conversion_isk_per_lp_sell",
    "sort_conversion_buy": "conversion_isk_per_lp_buy",
    "sort_conversion_avg_7d": "conversion_isk_per_lp_avg_7d",
    "sort_jita_sell": "jita_sell",
    "sort_jita_buy": "jita_buy",
    "sort_volume_1d": "volume_1d",
    "sort_volume_7d": "volume_7d",
    "sort_volume_30d": "volume_30d",
    "sort_acquisition": "acquisition_isk_per_unit",
    "sort_profit": "profit_vs_sell",
}

# Public API ordering aliases → IndustryLpStoreOfferEconomics field names.
API_ORDERING_MAP = {
    "type_name": "type_name",
    "currency_name": "currency_name",
    "lp_cost": "lp_cost",
    "isk_cost": "isk_cost",
    "quantity": "quantity",
    "other_cost": "other_cost",
    "jita_sell": "jita_sell",
    "jita_buy": "jita_buy",
    "jita_avg_7d": "jita_avg_7d",
    "conversion_sell": "conversion_isk_per_lp_sell",
    "conversion_buy": "conversion_isk_per_lp_buy",
    "conversion_avg_7d": "conversion_isk_per_lp_avg_7d",
    "volume_1d": "volume_1d",
    "volume_7d": "volume_7d",
    "volume_30d": "volume_30d",
    "updated_at": "offer_updated_at",
}

DEFAULT_API_ORDERING = "-conversion_sell"


def lp_econ_filters_active(params) -> bool:
    """True when exclude-useless or exclude-below-set is set to 0/1."""
    return any(
        params.get(name) in ("0", "1") for name in LP_ECON_FILTER_PARAMS
    )


def lp_offer_econ_cache_key() -> str:
    """
    Cache key for the full tracked-catalog economics map.

    Fingerprint includes tracked corps, offer count + max(updated_at),
    active currency default_isk_per_lp rates, and max Forge history date
    so offer sync / buyback edits / daily history refresh invalidate.
    """
    corp_ids = tracked_corporation_ids()
    corp_key = ",".join(str(c) for c in sorted(corp_ids)) or "none"
    if corp_ids:
        offer_stats = IndustryLpStoreOffer.objects.filter(
            corporation_id__in=corp_ids
        ).aggregate(n=Count("pk"), max_u=Max("updated_at"))
    else:
        offer_stats = {"n": 0, "max_u": None}
    currency_fp = (
        ",".join(
            f"{row.corporation_id}:{row.default_isk_per_lp}"
            for row in IndustryLoyaltyPoint.objects.filter(
                is_active=True
            ).order_by("corporation_id")
        )
        or "none"
    )
    hist_max = EveMarketItemHistory.objects.aggregate(m=Max("date"))["m"]
    n = int(offer_stats["n"] or 0)
    max_u = offer_stats["max_u"]
    max_u_s = max_u.isoformat() if max_u is not None else "none"
    hist_s = hist_max.isoformat() if hist_max is not None else "none"
    return (
        f"{_LP_OFFER_ECON_CACHE_PREFIX}:{corp_key}|n={n}|u={max_u_s}"
        f"|lp={currency_fp}|h={hist_s}"
    )


def get_tracked_offer_economics(
    *,
    request=None,
) -> Dict[int, LpStoreOfferEconomics]:
    """
    Resolve economics for all tracked LP store offers.

    Lookup order: request stash → Django cache → compute. Filters and
    list_display share the request-scoped map; the cross-request cache
    avoids recomputing when operators re-toggle exclude filters.
    """
    if request is not None:
        cached = getattr(request, LP_OFFER_ECON_ATTR, None)
        if cached is not None:
            return cached
    cache_key = lp_offer_econ_cache_key()
    economics = cache.get(cache_key)
    if economics is not None:
        if request is not None:
            setattr(request, LP_OFFER_ECON_ATTR, economics)
        return economics
    offers = list(
        IndustryLpStoreOffer.objects.filter(
            corporation_id__in=tracked_corporation_ids()
        )
    )
    economics = offer_economics_for_queryset(offers)
    if request is not None:
        setattr(request, LP_OFFER_ECON_ATTR, economics)
    cache.set(cache_key, economics, timeout=_LP_OFFER_ECON_CACHE_TTL)
    return economics


def ensure_lp_offer_econ_on_request(request):
    """Admin-facing alias: stash economics on the request."""
    return get_tracked_offer_economics(request=request)


def clear_lp_offer_econ_on_request(request) -> None:
    if hasattr(request, LP_OFFER_ECON_ATTR):
        delattr(request, LP_OFFER_ECON_ATTR)


def tracked_offers_queryset() -> QuerySet:
    """Base queryset for tracked LP currencies, with sort annotations."""
    qs = IndustryLpStoreOffer.objects.filter(
        corporation_id__in=tracked_corporation_ids()
    )
    return annotate_lp_store_offer_sort_fields(qs)


def _binary_type_filter(
    queryset: QuerySet,
    value: Optional[str],
    type_ids: Sequence[int],
) -> QuerySet:
    """Apply Yes/No exclude for offers that are or require given type ids."""
    if value not in ("0", "1") or not type_ids:
        return queryset
    req_offer_ids = IndustryLpStoreOfferRequiredItem.objects.filter(
        type_id__in=type_ids
    ).values("offer_id")
    match_q = Q(type_id__in=type_ids) | Q(pk__in=req_offer_ids)
    if value == "1":
        return queryset.exclude(match_q)
    return queryset.filter(match_q)


def apply_currency_filter(
    queryset: QuerySet, corporation_id: Optional[int]
) -> QuerySet:
    if corporation_id is None:
        return queryset
    return queryset.filter(corporation_id=int(corporation_id))


def apply_exclude_tags_filter(
    queryset: QuerySet, value: Optional[str]
) -> QuerySet:
    return _binary_type_filter(queryset, value, tag_type_ids())


def apply_exclude_supply_packages_filter(
    queryset: QuerySet, value: Optional[str]
) -> QuerySet:
    return _binary_type_filter(queryset, value, supply_package_type_ids())


def apply_exclude_chips_filter(
    queryset: QuerySet, value: Optional[str]
) -> QuerySet:
    return _binary_type_filter(queryset, value, chip_type_ids())


def apply_exclude_skins_filter(
    queryset: QuerySet, value: Optional[str]
) -> QuerySet:
    return _binary_type_filter(queryset, value, skin_type_ids())


def apply_exclude_useless_offers_filter(
    queryset: QuerySet,
    value: Optional[str],
    *,
    economics: Dict[int, LpStoreOfferEconomics],
) -> QuerySet:
    if value not in ("0", "1"):
        return queryset
    # values_list avoids loading full offer rows; economics already has data.
    pks = list(queryset.values_list("pk", flat=True))
    if not pks:
        return queryset
    peers = peer_stats_by_corporation(economics)
    useless: Set[int] = set()
    for pk in pks:
        econ = economics.get(pk)
        if econ is None:
            useless.add(pk)
            continue
        peer = peers.get(int(econ.corporation_id))
        if offer_is_useless(econ, peer):
            useless.add(pk)
    if value == "1":
        return queryset.exclude(pk__in=useless)
    return queryset.filter(pk__in=useless)


def apply_exclude_below_set_lp_price_filter(
    queryset: QuerySet,
    value: Optional[str],
    *,
    economics: Dict[int, LpStoreOfferEconomics],
    side: str = "sell",
) -> QuerySet:
    if value not in ("0", "1"):
        return queryset
    pks = list(queryset.values_list("pk", flat=True))
    if not pks:
        return queryset
    below: Set[int] = set()
    for pk in pks:
        econ = economics.get(pk)
        if econ is None or offer_is_below_set_lp_price(econ, side=side):
            below.add(pk)
    if value == "1":
        return queryset.exclude(pk__in=below)
    return queryset.filter(pk__in=below)


def apply_search(queryset: QuerySet, search_term: Optional[str]) -> QuerySet:
    """
    Search by offer_id / type_id / corporation_id or EveType name.

    Mirrors admin get_search_results: numeric field matches OR name matches
    within the already-filtered queryset (name hits cannot reintroduce
    excluded rows).
    """
    term = (search_term or "").strip()
    if not term:
        return queryset
    filtered_qs = queryset
    q = Q()
    if term.isdigit():
        n = int(term)
        q |= Q(offer_id=n) | Q(type_id=n) | Q(corporation_id=n)
    type_ids = list(
        EveType.objects.filter(name__icontains=term).values_list(
            "id", flat=True
        )
    )
    if type_ids:
        q |= Q(type_id__in=type_ids)
    if not q:
        return queryset.none()
    return filtered_qs.filter(q)


def apply_offer_filters(
    queryset: QuerySet,
    *,
    currency: Optional[int] = None,
    exclude_tags: Optional[str] = None,
    exclude_supply_packages: Optional[str] = None,
    exclude_chips: Optional[str] = None,
    exclude_skins: Optional[str] = None,
    exclude_useless_offers: Optional[str] = None,
    exclude_below_set_lp_price: Optional[str] = None,
    side: str = "sell",
    q: Optional[str] = None,
    economics: Optional[Dict[int, LpStoreOfferEconomics]] = None,
    request=None,
) -> QuerySet:
    """Apply all public/admin offer filters in admin-equivalent order."""
    qs = apply_currency_filter(queryset, currency)
    qs = apply_exclude_tags_filter(qs, exclude_tags)
    qs = apply_exclude_supply_packages_filter(qs, exclude_supply_packages)
    qs = apply_exclude_chips_filter(qs, exclude_chips)
    qs = apply_exclude_skins_filter(qs, exclude_skins)

    needs_econ = exclude_useless_offers in (
        "0",
        "1",
    ) or exclude_below_set_lp_price in ("0", "1")
    if needs_econ:
        if economics is None:
            economics = get_tracked_offer_economics(request=request)
        qs = apply_exclude_useless_offers_filter(
            qs, exclude_useless_offers, economics=economics
        )
        qs = apply_exclude_below_set_lp_price_filter(
            qs,
            exclude_below_set_lp_price,
            economics=economics,
            side=side if side in ("sell", "buy", "avg_7d") else "sell",
        )

    qs = apply_search(qs, q)
    return qs


def sort_offers_by_econ(
    queryset: QuerySet,
    *,
    ordering_terms: Sequence[Tuple[str, bool]],
    economics: Dict[int, LpStoreOfferEconomics],
) -> QuerySet:
    """
    Re-order queryset by economics attributes.

    ``ordering_terms`` is a sequence of (admin_annotation_field, descending)
    where field is a key in LP_OFFER_ECON_ORDER_ATTR. Uses the first term
    only (matches typical single-column admin sort).
    """
    if not ordering_terms:
        return queryset
    field, descending = ordering_terms[0]
    attr = LP_OFFER_ECON_ORDER_ATTR[field]

    def sort_key(obj):
        econ = economics.get(obj.pk) if economics else None
        if econ is None:
            return (1, 0.0)
        value = getattr(econ, attr, None)
        if value is None:
            return (1, 0.0)
        return (0, float(value))

    ordered = sorted(queryset.order_by("pk"), key=sort_key, reverse=descending)
    if not ordered:
        return queryset.order_by()
    pk_order = [obj.pk for obj in ordered]
    preserved = Case(
        *[When(pk=pk, then=pos) for pos, pk in enumerate(pk_order)],
        output_field=IntegerField(),
    )
    return (
        queryset.order_by()
        .filter(pk__in=pk_order)
        .annotate(_lp_econ_ord=preserved)
        .order_by("_lp_econ_ord")
    )


def parse_api_ordering(
    ordering: Optional[str],
) -> Tuple[bool, str]:
    """
    Parse API ordering string.

    Returns (descending, snapshot_field).
    """
    raw = (ordering or "").strip() or DEFAULT_API_ORDERING
    descending = raw.startswith("-")
    key = raw[1:] if descending else raw
    field = API_ORDERING_MAP.get(key)
    if field is None:
        raw = DEFAULT_API_ORDERING
        descending = raw.startswith("-")
        key = raw[1:] if descending else raw
        field = API_ORDERING_MAP[key]
    return descending, field


def order_api_offers(
    queryset: QuerySet,
    *,
    ordering: Optional[str] = None,
    economics: Dict[int, LpStoreOfferEconomics],
) -> QuerySet:
    """Legacy helper retained for admin-style callers; prefer snapshot query."""
    descending, field = parse_api_ordering(ordering)
    # Map snapshot field names back to live sort when possible.
    attr = field
    if field == "offer_updated_at":
        prefix = "-" if descending else ""
        return queryset.order_by(f"{prefix}updated_at", "pk")
    if field in ("lp_cost", "isk_cost", "quantity"):
        prefix = "-" if descending else ""
        return queryset.order_by(f"{prefix}{field}", "pk")

    def sort_key(obj):
        econ = economics.get(obj.pk) if economics else None
        if econ is None:
            return (1, "")
        # Snapshot conversion_* map onto dataclass attrs.
        econ_attr = {
            "conversion_isk_per_lp_sell": "conversion_isk_per_lp_sell",
            "conversion_isk_per_lp_buy": "conversion_isk_per_lp_buy",
            "conversion_isk_per_lp_avg_7d": "conversion_isk_per_lp_avg_7d",
            "type_name": "type_name",
            "currency_name": "currency_name",
            "other_cost": "other_cost",
            "jita_sell": "jita_sell",
            "jita_buy": "jita_buy",
            "jita_avg_7d": "jita_avg_7d",
            "volume_1d": "volume_1d",
            "volume_7d": "volume_7d",
            "volume_30d": "volume_30d",
        }.get(attr, attr)
        value = getattr(econ, econ_attr, None)
        if value is None:
            return (1, "")
        if isinstance(value, str):
            return (0, value.lower())
        return (0, float(value))

    ordered = sorted(queryset.order_by("pk"), key=sort_key, reverse=descending)
    if not ordered:
        return queryset.order_by()
    pk_order = [obj.pk for obj in ordered]
    preserved = Case(
        *[When(pk=pk, then=pos) for pos, pk in enumerate(pk_order)],
        output_field=IntegerField(),
    )
    return (
        queryset.order_by()
        .filter(pk__in=pk_order)
        .annotate(_lp_econ_ord=preserved)
        .order_by("_lp_econ_ord")
    )


def display_type_name(econ: LpStoreOfferEconomics) -> str:
    """Public display name, including (BPC) for blueprint copies."""
    if econ.kind == "blueprint" and econ.market_type_id != econ.type_id:
        return f"{econ.market_type_name} (BPC)"
    return econ.type_name


def display_type_id(econ: LpStoreOfferEconomics) -> int:
    return econ.type_id


@dataclass(frozen=True)
class LpStoreOffersPage:
    rows: List[IndustryLpStoreOfferEconomics]
    total: int
    limit: int
    offset: int


def _apply_snapshot_binary_flag(
    queryset: QuerySet,
    value: Optional[str],
    field: str,
) -> QuerySet:
    if value not in ("0", "1"):
        return queryset
    if value == "1":
        return queryset.exclude(**{field: True})
    return queryset.filter(**{field: True})


def _apply_snapshot_search(
    queryset: QuerySet, search_term: Optional[str]
) -> QuerySet:
    term = (search_term or "").strip()
    if not term:
        return queryset
    q = Q(type_name__icontains=term)
    if term.isdigit():
        n = int(term)
        q |= Q(esi_offer_id=n) | Q(type_id=n) | Q(corporation_id=n)
    return queryset.filter(q)


def normalize_offers_side(side: Optional[str]) -> str:
    if side == "buy":
        return "buy"
    if side == "avg_7d":
        return "avg_7d"
    return "sell"


_CONVERSION_ORDER_RE = re.compile(r"conversion_(?:sell|buy|avg_7d)")
_SIDE_CONVERSION_KEY = {
    "sell": "conversion_sell",
    "buy": "conversion_buy",
    "avg_7d": "conversion_avg_7d",
}
_SIDE_BELOW_SET_FLAG = {
    "sell": "is_below_set_lp_price",
    "buy": "is_below_set_lp_price_buy",
    "avg_7d": "is_below_set_lp_price_avg_7d",
}


def normalize_offers_ordering(ordering: Optional[str], side: str) -> str:
    """Keep conversion sort aligned with the active price side."""
    raw = (ordering or DEFAULT_API_ORDERING).strip() or DEFAULT_API_ORDERING
    target = _SIDE_CONVERSION_KEY.get(side, "conversion_sell")
    return _CONVERSION_ORDER_RE.sub(target, raw)


def query_lp_store_offers(
    *,
    currency: Optional[int] = None,
    exclude_tags: Optional[str] = None,
    exclude_supply_packages: Optional[str] = None,
    exclude_chips: Optional[str] = None,
    exclude_skins: Optional[str] = None,
    exclude_useless_offers: Optional[str] = None,
    exclude_below_set_lp_price: Optional[str] = None,
    side: Optional[str] = None,
    q: Optional[str] = None,
    ordering: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    request=None,
) -> LpStoreOffersPage:
    """Filter and sort the hourly LP offer economics snapshot.

    When ``limit`` is None, returns the full filtered set (snapshot is small).
    """
    # Unused request kept for call-site compatibility.
    _ = request
    offers_side = normalize_offers_side(side)
    qs = IndustryLpStoreOfferEconomics.objects.all()
    if currency is not None:
        qs = qs.filter(corporation_id=int(currency))
    qs = _apply_snapshot_binary_flag(qs, exclude_tags, "involves_tag")
    qs = _apply_snapshot_binary_flag(
        qs, exclude_supply_packages, "involves_supply_package"
    )
    qs = _apply_snapshot_binary_flag(qs, exclude_chips, "involves_chip")
    qs = _apply_snapshot_binary_flag(qs, exclude_skins, "involves_skin")
    qs = _apply_snapshot_binary_flag(qs, exclude_useless_offers, "is_useless")
    below_flag = _SIDE_BELOW_SET_FLAG.get(offers_side, "is_below_set_lp_price")
    qs = _apply_snapshot_binary_flag(
        qs, exclude_below_set_lp_price, below_flag
    )
    qs = _apply_snapshot_search(qs, q)

    offset = max(0, int(offset))
    descending, field = parse_api_ordering(
        normalize_offers_ordering(ordering, offers_side)
    )
    # Nulls last so missing rates sink when sorting best conversions first.
    if descending:
        qs = qs.order_by(F(field).desc(nulls_last=True), "offer_id")
    else:
        qs = qs.order_by(F(field).asc(nulls_last=True), "offer_id")

    total = qs.count()
    if limit is None:
        page = list(qs[offset:])
        effective_limit = len(page)
    else:
        effective_limit = max(1, min(int(limit), 5000))
        page = list(qs[offset : offset + effective_limit])
    return LpStoreOffersPage(
        rows=page,
        total=total,
        limit=effective_limit,
        offset=offset,
    )


__all__ = [
    "API_ORDERING_MAP",
    "DEFAULT_API_ORDERING",
    "LP_ECON_FILTER_PARAMS",
    "LP_OFFER_ECON_ATTR",
    "LP_OFFER_ECON_ORDER_ATTR",
    "LpStoreOffersPage",
    "apply_currency_filter",
    "apply_exclude_below_set_lp_price_filter",
    "apply_exclude_chips_filter",
    "apply_exclude_skins_filter",
    "apply_exclude_supply_packages_filter",
    "apply_exclude_tags_filter",
    "apply_exclude_useless_offers_filter",
    "apply_offer_filters",
    "apply_search",
    "clear_lp_offer_econ_on_request",
    "display_type_id",
    "display_type_name",
    "ensure_lp_offer_econ_on_request",
    "get_tracked_offer_economics",
    "lp_econ_filters_active",
    "lp_offer_econ_cache_key",
    "normalize_offers_ordering",
    "normalize_offers_side",
    "order_api_offers",
    "parse_api_ordering",
    "query_lp_store_offers",
    "sort_offers_by_econ",
    "tracked_offers_queryset",
]
