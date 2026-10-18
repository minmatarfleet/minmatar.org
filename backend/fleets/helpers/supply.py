"""
Availability of a fleet's ships at its staging location: outstanding
contracts per fit and how many complete fits the local sell orders cover.
"""

from dataclasses import dataclass, field

from django.db.models import Count, Sum

from eveuniverse.models import EveType
from fittings.eft import purchase_items
from market.helpers.contract_stock import outstanding_stock_q
from market.models import EveMarketContract, EveMarketItemOrder

from fleets.helpers.composition import CompositionEntry, fleet_composition


@dataclass
class SupplyEntry:
    key: str
    fitting_id: int | None
    fleet_fitting_id: int | None
    contracts: int | None = None
    market_fits: int | None = None
    market_missing: list = field(default_factory=list)


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

    needed_by_key = {e.key: purchase_items(e.eft_format) for e in entries}
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
