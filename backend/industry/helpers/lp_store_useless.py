"""Exclude-useless-offers screening for LP store catalogs.

An offer is useless when it fails any of:
1. Stockpile usefulness — cannot clear meaningful LP/ISK from a 250k–1M
   dump, or Forge 30d volume cannot absorb that dump.
2. Profit — conversion sell ISK/LP is null or ≤ alliance buyback
   (``default_isk_per_lp``), or acquisition ≥ jita sell.
3. Below peer average — conversion sell < ratio × median of
   volume-viable same-currency peers.
4. Volume / volatility — negligible Forge 30d volume (null or < 1),
   missing jita buy, or wide relative spread.

Volatility/depth proxy: we do not store Fuzzwork "5% Volume" order-book
depth (qty within 5% of best). Missing buy or ``(sell−buy)/sell`` above
``USELESS_MAX_RELATIVE_SPREAD`` stands in for shallow books; 30d history
volume remains the liquidity floor.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set

from industry.helpers.lp_store_economics import (
    NEGLIGIBLE_LP_FORGE_VOLUME_30D,
    LpStoreOfferEconomics,
    offer_economics_for_queryset,
)
from industry.models import IndustryLpStoreOffer

# ---------------------------------------------------------------------------
# Tunable thresholds
# ---------------------------------------------------------------------------
# Typical alliance LP stockpile band for conversion-desk dumps.
USELESS_STOCKPILE_LP_LOW = 250_000
USELESS_STOCKPILE_LP_HIGH = 1_000_000
# Absolute ISK floor from dumping LOW stockpile (or one purchase when LP
# cost exceeds LOW but not HIGH). ~200 isk/lp × 250k LP ≈ 50M — soft floor
# for "trivial cash"; offers below buyback still fail the profit rule.
USELESS_MIN_ISK_FROM_STOCKPILE = 50_000_000
# Conversion sell below this fraction of same-currency median among
# volume-viable peers → significantly below average.
USELESS_BELOW_MEDIAN_RATIO = 0.75
# Relative bid/ask spread (sell − buy) / sell. Above this ⇒ too thin /
# volatile (depth proxy; see module docstring).
USELESS_MAX_RELATIVE_SPREAD = 0.40


@dataclass(frozen=True)
class CurrencyPeerStats:
    """Per-currency stats for below-average checks among volume-viable peers."""

    median_conversion_sell: Optional[float]
    viable_count: int


def _purchases_for_stockpile(lp_cost: int, stockpile_lp: int) -> int:
    if lp_cost <= 0:
        return 0
    return int(stockpile_lp) // int(lp_cost)


def _stockpile_dump_lp_spent(lp_cost: int) -> Optional[int]:
    """
    LP spent when dumping a typical stockpile through this offer.

    Prefer a LOW-band dump when at least one purchase fits; otherwise one
    purchase if the offer is still affordable from the HIGH band.
    """
    if lp_cost <= 0:
        return None
    low_buys = _purchases_for_stockpile(lp_cost, USELESS_STOCKPILE_LP_LOW)
    if low_buys >= 1:
        return low_buys * lp_cost
    high_buys = _purchases_for_stockpile(lp_cost, USELESS_STOCKPILE_LP_HIGH)
    if high_buys >= 1:
        return lp_cost
    return None


def _stockpile_dump_units(econ: LpStoreOfferEconomics) -> int:
    """Units from dumping HIGH stockpile through this offer."""
    buys = _purchases_for_stockpile(econ.lp_cost, USELESS_STOCKPILE_LP_HIGH)
    return buys * max(int(econ.quantity), 1)


def _relative_spread(
    jita_sell: Optional[int], jita_buy: Optional[int]
) -> Optional[float]:
    if jita_sell is None or jita_buy is None or jita_sell <= 0:
        return None
    return (float(jita_sell) - float(jita_buy)) / float(jita_sell)


def _has_viable_forge_volume(econ: LpStoreOfferEconomics) -> bool:
    return (
        econ.volume_30d is not None
        and int(econ.volume_30d) >= NEGLIGIBLE_LP_FORGE_VOLUME_30D
    )


def peer_stats_by_corporation(
    economics: Dict[int, LpStoreOfferEconomics],
) -> Dict[int, CurrencyPeerStats]:
    """
    Median conversion ISK/LP (sell) per corporation among volume-viable offers.

    Peers need Forge 30d volume and a finite conversion_isk_per_lp_sell.
    """
    by_corp: Dict[int, List[float]] = {}
    for econ in economics.values():
        if not _has_viable_forge_volume(econ):
            continue
        rate = econ.conversion_isk_per_lp_sell
        if rate is None:
            continue
        by_corp.setdefault(int(econ.corporation_id), []).append(float(rate))

    out: Dict[int, CurrencyPeerStats] = {}
    for corp_id, rates in by_corp.items():
        out[corp_id] = CurrencyPeerStats(
            median_conversion_sell=float(statistics.median(rates)),
            viable_count=len(rates),
        )
    return out


def offer_fails_stockpile_usefulness(econ: LpStoreOfferEconomics) -> bool:
    """
    Offer cannot meaningfully clear a 250k–1M LP stockpile.

    True when: unaffordable from 1M LP; ISK from a typical dump is below
    ``USELESS_MIN_ISK_FROM_STOCKPILE``; or 30d Forge volume cannot absorb
    units from dumping the HIGH stockpile through this offer.
    """
    if econ.lp_cost <= 0:
        return True
    if _purchases_for_stockpile(econ.lp_cost, USELESS_STOCKPILE_LP_HIGH) < 1:
        return True

    lp_spent = _stockpile_dump_lp_spent(econ.lp_cost)
    rate = econ.conversion_isk_per_lp_sell
    if lp_spent is not None and rate is not None:
        if float(rate) * float(lp_spent) < USELESS_MIN_ISK_FROM_STOCKPILE:
            return True

    if _has_viable_forge_volume(econ):
        units = _stockpile_dump_units(econ)
        if units > int(econ.volume_30d or 0):
            return True
    return False


def offer_fails_profit(econ: LpStoreOfferEconomics) -> bool:
    """
    Conversion sell ISK/LP at or below alliance buyback (opportunity cost).

    Null conversion (missing prices / costs) counts as not profitable.
    Also true when acquisition cost ≥ jita sell when both are known.
    """
    rate = econ.conversion_isk_per_lp_sell
    buyback = econ.isk_per_lp
    if rate is None:
        return True
    if buyback is not None and float(rate) <= float(buyback):
        return True
    if (
        econ.acquisition_isk_per_unit is not None
        and econ.jita_sell is not None
        and int(econ.acquisition_isk_per_unit) >= int(econ.jita_sell)
    ):
        return True
    return False


def offer_fails_below_peer_average(
    econ: LpStoreOfferEconomics,
    peers_stats: Optional[CurrencyPeerStats],
) -> bool:
    """Conversion sell meaningfully below median of volume-viable peers."""
    if peers_stats is None or peers_stats.median_conversion_sell is None:
        return False
    if peers_stats.viable_count < 1:
        return False
    rate = econ.conversion_isk_per_lp_sell
    if rate is None:
        return False
    floor = USELESS_BELOW_MEDIAN_RATIO * float(
        peers_stats.median_conversion_sell
    )
    return float(rate) < floor


def offer_fails_volume_or_volatility(econ: LpStoreOfferEconomics) -> bool:
    """
    Negligible Forge volume and/or too-wide / missing bid-ask.

    Volume: 30d null or < ``NEGLIGIBLE_LP_FORGE_VOLUME_30D``.
    Volatility proxy: jita buy missing, or relative spread above
    ``USELESS_MAX_RELATIVE_SPREAD`` (stand-in for Fuzzwork 5% depth).
    """
    if not _has_viable_forge_volume(econ):
        return True
    if econ.jita_buy is None:
        return True
    spread = _relative_spread(econ.jita_sell, econ.jita_buy)
    if spread is not None and spread > USELESS_MAX_RELATIVE_SPREAD:
        return True
    return False


def offer_is_useless(
    econ: LpStoreOfferEconomics,
    peers_stats: Optional[CurrencyPeerStats] = None,
) -> bool:
    """
    True when the offer is useless for LP conversion desk screening.

    See module docstring for the four criteria (OR).
    """
    return (
        offer_fails_stockpile_usefulness(econ)
        or offer_fails_profit(econ)
        or offer_fails_below_peer_average(econ, peers_stats)
        or offer_fails_volume_or_volatility(econ)
    )


def useless_offer_pks(
    offers: Iterable[IndustryLpStoreOffer],
    *,
    economics: Optional[Dict[int, LpStoreOfferEconomics]] = None,
) -> Set[int]:
    """Compute primary keys of useless offers for an admin filter queryset.

    Pass a precomputed ``economics`` map (e.g. request-scoped full catalog)
    to avoid recomputing offer_economics_for_queryset. Peer medians always
    come from that map so they stay stable across stacked admin filters.
    """
    rows = list(offers)
    if not rows:
        return set()
    if economics is None:
        economics = offer_economics_for_queryset(rows)
    peers = peer_stats_by_corporation(economics)
    useless: Set[int] = set()
    for offer in rows:
        pk = offer.pk
        if pk is None:
            continue
        econ = economics.get(pk)
        if econ is None:
            useless.add(pk)
            continue
        if offer_is_useless(econ, peers.get(int(econ.corporation_id))):
            useless.add(pk)
    return useless
