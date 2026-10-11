"""
Availability of a fleet's ships at its staging location: outstanding
contracts per fit and how many complete fits the local sell orders cover.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from django.db.models import Count, Sum

from eveuniverse.models import EveType
from fittings.models import EveFitting
from market.helpers.contract_stock import outstanding_stock_q
from market.models import EveMarketContract, EveMarketItemOrder

from fleets.helpers.composition import CompositionEntry, fleet_composition

_QTY_SUFFIX_RE = re.compile(r"^(?P<name>.+?)\s+x(?P<qty>\d+)$")


@dataclass
class SupplyEntry:
    key: str
    fitting_id: int | None
    fleet_fitting_id: int | None
    contracts: int | None = None
    market_fits: int | None = None
    market_missing: list = field(default_factory=list)


def eft_purchase_items(eft_format: str) -> Counter:
    """
    Items needed to buy one copy of a fit: the hull plus every fitted module
    and rig. Charges, drones and cargo (``Name xN`` lines) are left out so a
    fit still counts as available when only ammo is missing.
    """
    needed: Counter = Counter()
    lines = (eft_format or "").strip().splitlines()
    if not lines:
        return needed
    ship = EveFitting.ship_name_from_eft(eft_format)
    if ship:
        needed[ship] += 1
    for raw in lines[1:]:
        line = raw.strip()
        if (
            not line
            or line.startswith("[Empty ")
            or _QTY_SUFFIX_RE.match(line)
        ):
            continue
        module = line.split(",", 1)[0].strip()
        if module:
            needed[module] += 1
    return needed


def _sell_order_stock(location, names: set[str]) -> dict[str, int]:
    """name -> units on sell orders at ``location`` for the given item names."""
    if not names:
        return {}
    rows = (
        EveMarketItemOrder.objects.filter(
            location=location, is_buy_order=False, item__name__in=names
        )
        .order_by()
        .values("item__name")
        .annotate(total=Sum("quantity"))
    )
    stock = {row["item__name"]: int(row["total"] or 0) for row in rows}
    return stock


def _contract_counts(location, fitting_ids: set[int]) -> dict[int, int]:
    if not fitting_ids:
        return {}
    # order_by() clears Meta.ordering so it can't leak into the GROUP BY.
    rows = (
        EveMarketContract.objects.filter(outstanding_stock_q())
        .filter(location=location, fitting_id__in=fitting_ids)
        .order_by()
        .values("fitting_id")
        .annotate(total=Count("id"))
    )
    return {row["fitting_id"]: int(row["total"] or 0) for row in rows}


def fleet_supply(eve_fleet) -> list[SupplyEntry]:
    """
    One entry per composition ship. Contracts are only counted for catalog
    fits; market coverage is computed for every fit with an EFT and left
    None when the staging location has no market data.
    """
    location = eve_fleet.location
    entries: list[CompositionEntry] = fleet_composition(eve_fleet)
    if location is None:
        return [
            SupplyEntry(e.key, e.fitting_id, e.fleet_fitting_id)
            for e in entries
        ]

    needed_by_key = {e.key: eft_purchase_items(e.eft_format) for e in entries}
    all_names = set().union(*(set(n) for n in needed_by_key.values()))
    known_names = set(
        EveType.objects.filter(name__in=all_names).values_list(
            "name", flat=True
        )
    )
    has_market_data = (
        location.market_active
        or EveMarketItemOrder.objects.filter(
            location=location, is_buy_order=False
        ).exists()
    )
    stock = _sell_order_stock(location, known_names) if has_market_data else {}
    contracts = _contract_counts(
        location, {e.fitting_id for e in entries if e.fitting_id}
    )

    result = []
    for entry in entries:
        row = SupplyEntry(entry.key, entry.fitting_id, entry.fleet_fitting_id)
        if entry.fitting_id:
            row.contracts = contracts.get(entry.fitting_id, 0)
        needed = needed_by_key[entry.key]
        if has_market_data and needed:
            fits = min(
                stock.get(name, 0) // qty for name, qty in needed.items()
            )
            row.market_fits = fits
            row.market_missing = sorted(
                name for name in needed if stock.get(name, 0) <= 0
            )
        result.append(row)
    return result
