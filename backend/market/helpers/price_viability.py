"""Reusable price-viability policy for market listings and related views.

Default rule: an offered price is viable when it is at most ``DEFAULT_MAX_MARKUP_PCT``
above the baseline price, unless the baseline is missing/invalid or below
``DEFAULT_BASELINE_PRICE_FLOOR`` (cheap items always count as viable).
"""

from __future__ import annotations

from typing import NamedTuple

# Listed-within-reason defaults used across market ops, admin sell orders, etc.
DEFAULT_MAX_MARKUP_PCT = 20
DEFAULT_BASELINE_PRICE_FLOOR = 1_000_000


class PriceViabilityPolicy(NamedTuple):
    """Configurable thresholds for whether an offered price is viable."""

    max_markup_pct: int = DEFAULT_MAX_MARKUP_PCT
    baseline_price_floor: int = DEFAULT_BASELINE_PRICE_FLOOR


DEFAULT_PRICE_VIABILITY_POLICY = PriceViabilityPolicy()


def is_price_viable(
    offered_price,
    baseline_price: int | None,
    *,
    policy: PriceViabilityPolicy | None = None,
    max_markup_pct: int | None = None,
    baseline_price_floor: int | None = None,
) -> bool:
    """
    Return True if ``offered_price`` counts as price-viable vs ``baseline_price``.

    Thresholds can be supplied via ``policy`` or individual overrides. When both
    are given, individual overrides win. Missing/invalid baselines, or baselines
    below the floor, always count as viable.
    """
    active = policy or DEFAULT_PRICE_VIABILITY_POLICY
    markup_pct = (
        max_markup_pct if max_markup_pct is not None else active.max_markup_pct
    )
    floor = (
        baseline_price_floor
        if baseline_price_floor is not None
        else active.baseline_price_floor
    )

    if baseline_price is None or baseline_price <= 0:
        return True
    if baseline_price < floor:
        return True
    price = int(offered_price)
    max_viable = baseline_price * (100 + markup_pct) // 100
    return price <= max_viable


# Backward-compatible aliases for call sites that historically used sell-order names.
REASONABLE_MARKUP_MAX_PCT = DEFAULT_MAX_MARKUP_PCT
REASONABLE_JITA_PRICE_FLOOR = DEFAULT_BASELINE_PRICE_FLOOR


def order_quantity_counts_as_reasonable(
    order_price,
    jita_sell_price: int | None,
    *,
    policy: PriceViabilityPolicy | None = None,
    max_markup_pct: int | None = None,
    baseline_price_floor: int | None = None,
) -> bool:
    """Alias of :func:`is_price_viable` for sell-order aggregation callers."""
    return is_price_viable(
        order_price,
        jita_sell_price,
        policy=policy,
        max_markup_pct=max_markup_pct,
        baseline_price_floor=baseline_price_floor,
    )
