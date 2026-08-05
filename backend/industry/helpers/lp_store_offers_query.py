"""Public LP store offer economics snapshot query (filter / sort / page)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from django.db.models import F, Q, QuerySet

from industry.models import IndustryLpStoreOfferEconomics

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


@dataclass(frozen=True)
class LpStoreOffersPage:
    rows: List[IndustryLpStoreOfferEconomics]
    total: int
    limit: int
    offset: int


def normalize_offers_side(side: Optional[str]) -> str:
    if side == "buy":
        return "buy"
    if side == "avg_7d":
        return "avg_7d"
    return "sell"


def normalize_offers_ordering(ordering: Optional[str], side: str) -> str:
    """Keep conversion sort aligned with the active price side."""
    raw = (ordering or DEFAULT_API_ORDERING).strip() or DEFAULT_API_ORDERING
    target = _SIDE_CONVERSION_KEY.get(side, "conversion_sell")
    return _CONVERSION_ORDER_RE.sub(target, raw)


def parse_api_ordering(
    ordering: Optional[str],
) -> Tuple[bool, str]:
    """Parse API ordering string. Returns (descending, snapshot_field)."""
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
) -> LpStoreOffersPage:
    """Filter and sort the hourly LP offer economics snapshot.

    When ``limit`` is None, returns the full filtered set (snapshot is small).
    """
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
    "LpStoreOffersPage",
    "normalize_offers_ordering",
    "normalize_offers_side",
    "parse_api_ordering",
    "query_lp_store_offers",
]
