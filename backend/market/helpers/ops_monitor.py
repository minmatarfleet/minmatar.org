"""Ops monitor queues for staging supply health (read-only)."""

from __future__ import annotations

from django.db.models import Count, DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from eveuniverse.models import EveType

from eveonline.models import EveLocation
from market.helpers.contract_stock import outstanding_stock_q
from market.helpers.item_ships import item_ships_by_location
from market.helpers.price_viability import is_price_viable
from market.helpers.pricing import get_prices_by_type_id
from market.helpers.readiness import fitting_readiness, shortfall
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
)
from market.models.item import (
    EveMarketItemOrder,
    get_effective_item_expectations_bulk,
)

# Matches frontend SHIP_TYPES_SORTED — small hulls first.
SHIP_GROUP_ORDER = [
    "Frigate",
    "Electronic Attack Ship",
    "Assault Frigate",
    "Logistics Frigate",
    "Covert Ops",
    "Stealth Bomber",
    "Interceptor",
    "Destroyer",
    "Interdictor",
    "Command Destroyer",
    "Tactical Destroyer",
    "Cruiser",
    "Heavy Assault Cruiser",
    "Heavy Interdiction Cruiser",
    "Logistics",
    "Logistics Crusiers",
    "Strategic Cruiser",
    "Recon Ship",
    "Force Recon Ship",
    "Combat Recon Ship",
    "Battlecruiser",
    "Combat Battlecruiser",
    "Attack Battlecruiser",
    "Command Ship",
    "Battleship",
    "Marauder",
    "Black Ops",
    "Capital",
    "Dreadnought",
    "Lancer Dreadnought",
    "Carrier",
    "Force Auxiliary",
    "Super Capital",
    "Super Carrier",
    "Titan",
    "Mining Frigate",
    "Expedition Frigate",
    "Mining Barge",
    "Industrial",
    "Transport Ship",
    "Freighter",
    "Jump Freighters",
    "Industrial Command Ship",
    "Unclassified",
]


def _ship_size_rank(group_name: str | None) -> int:
    if not group_name:
        return len(SHIP_GROUP_ORDER)
    try:
        return SHIP_GROUP_ORDER.index(group_name)
    except ValueError:
        return len(SHIP_GROUP_ORDER)


def build_ops_monitor(*, location_id: int | None = None) -> dict:  # noqa: C901
    """
    Monitor queues for one or all market-active locations.

    Config stays in admin; this is triage data only.
    """
    locations = EveLocation.objects.filter(market_active=True)
    if location_id is not None:
        locations = locations.filter(location_id=location_id)
    locations = list(locations)
    if not locations:
        return {
            "synced_at": timezone.now().isoformat(),
            "contracts_synced_at": None,
            "orders_synced_at": None,
            "understocked_contracts": [],
            "sell_gaps": [],
            "summary": {
                "understocked_contracts": 0,
                "sell_gaps": 0,
                "contracts_health_pct": None,
                "sell_orders_health_pct": None,
                "sell_orders_viability_pct": None,
                "overall_health_pct": None,
                "contract_targets": 0,
                "contract_fulfilled": 0,
                "sell_order_targets": 0,
                "sell_order_fulfilled": 0,
                "sell_order_viable_fulfilled": 0,
                "contracts_isk": 0.0,
                "sell_orders_isk": 0.0,
                "total_isk_on_market": 0.0,
            },
        }

    location_pks = [loc.pk for loc in locations]
    location_by_pk = {loc.pk: loc for loc in locations}

    outstanding = {
        (row["location_id"], row["fitting_id"]): row["count"]
        for row in EveMarketContract.objects.filter(
            outstanding_stock_q(),
            location_id__in=location_pks,
        )
        .values("location_id", "fitting_id")
        .annotate(count=Count("id"))
    }

    expectations = list(
        EveMarketContractExpectation.objects.filter(
            location_id__in=location_pks
        ).select_related("fitting", "location")
    )

    understocked_contracts = []
    contract_fill_ratios: list[float] = []
    for expectation in expectations:
        current = outstanding.get(
            (expectation.location_id, expectation.fitting_id), 0
        )
        if expectation.quantity > 0:
            contract_fill_ratios.append(
                min(1.0, current / expectation.quantity)
            )
        level = fitting_readiness(current, expectation.quantity)
        if level in ("ready", "unknown"):
            continue
        understocked_contracts.append(
            {
                "location_id": expectation.location.location_id,
                "location_name": expectation.location.location_name,
                "short_name": expectation.location.short_name or "",
                "fitting_id": expectation.fitting_id,
                "fitting_name": expectation.fitting.name,
                "ship_id": expectation.fitting.ship_id,
                "current_quantity": current,
                "expected_quantity": expectation.quantity,
                "shortfall": shortfall(current, expectation.quantity),
                "readiness": level,
                "expectation_id": expectation.id,
            }
        )

    ship_ids = {row["ship_id"] for row in understocked_contracts}
    group_by_ship_id = dict(
        EveType.objects.filter(id__in=ship_ids).values_list(
            "id", "eve_group__name"
        )
    )

    understocked_contracts.sort(
        key=lambda row: (
            _ship_size_rank(group_by_ship_id.get(row["ship_id"])),
            0 if row["readiness"] == "empty" else 1,
            -row["shortfall"],
            row["fitting_name"],
        )
    )

    effective = get_effective_item_expectations_bulk(locations)
    ships_by_item = item_ships_by_location(locations)
    sell_gaps = []
    sell_fill_ratios: list[float] = []
    sell_viable_fill_ratios: list[float] = []
    all_names = set()
    for name_map in effective.values():
        all_names.update(name_map.keys())
    type_by_name = {
        t.name: t for t in EveType.objects.filter(name__in=all_names)
    }
    target_type_ids = [t.id for t in type_by_name.values()]
    baseline_by_type = (
        get_prices_by_type_id(target_type_ids) if target_type_ids else {}
    )
    stock_by_loc_item: dict[tuple[int, int], int] = {}
    viable_by_loc_item: dict[tuple[int, int], int] = {}
    for order in EveMarketItemOrder.objects.filter(
        location_id__in=location_pks,
        is_buy_order=False,
        item_id__in=target_type_ids,
    ).values("location_id", "item_id", "price", "quantity"):
        key = (order["location_id"], order["item_id"])
        quantity = order["quantity"] or 0
        stock_by_loc_item[key] = stock_by_loc_item.get(key, 0) + quantity
        if is_price_viable(
            order["price"], baseline_by_type.get(order["item_id"])
        ):
            viable_by_loc_item[key] = viable_by_loc_item.get(key, 0) + quantity

    sell_targets = 0
    sell_fulfilled = 0
    sell_viable_fulfilled = 0
    for loc_pk, name_map in effective.items():
        loc = location_by_pk[loc_pk]
        for name, desired in name_map.items():
            if desired <= 0:
                continue
            eve_type = type_by_name.get(name)
            if eve_type is None:
                continue
            current = stock_by_loc_item.get((loc_pk, eve_type.id), 0)
            viable = viable_by_loc_item.get((loc_pk, eve_type.id), 0)
            sell_targets += 1
            sell_fill_ratios.append(min(1.0, current / desired))
            sell_viable_fill_ratios.append(min(1.0, viable / desired))
            if current >= desired:
                sell_fulfilled += 1
            if viable >= desired:
                sell_viable_fulfilled += 1
            needed = shortfall(viable, desired)
            # Critical viability gaps: under 50% of target at a viable price.
            if viable >= desired * 0.5:
                continue
            sell_gaps.append(
                {
                    "location_id": loc.location_id,
                    "location_name": loc.location_name,
                    "short_name": loc.short_name or "",
                    "type_id": eve_type.id,
                    "item_name": name,
                    "current_quantity": current,
                    "viable_quantity": viable,
                    "expected_quantity": desired,
                    "shortfall": needed,
                    "ships": ships_by_item.get(loc_pk, {}).get(name, []),
                }
            )

    sell_gaps.sort(key=lambda row: (-row["shortfall"], row["item_name"]))

    contract_targets = len(contract_fill_ratios)
    contract_fulfilled = sum(
        1 for ratio in contract_fill_ratios if ratio >= 1.0
    )
    contracts_health_pct = _health_pct(contract_fill_ratios)
    sell_orders_health_pct = _health_pct(sell_fill_ratios)
    sell_orders_viability_pct = _health_pct(sell_viable_fill_ratios)
    overall_health_pct = _combined_health(
        contracts_health_pct, sell_orders_health_pct
    )

    latest_contract = (
        EveMarketContract.objects.filter(location_id__in=location_pks)
        .order_by("-last_updated")
        .values_list("last_updated", flat=True)
        .first()
    )
    latest_order = (
        EveMarketItemOrder.objects.filter(location_id__in=location_pks)
        .order_by("-created_at")
        .values_list("created_at", flat=True)
        .first()
    )

    contracts_isk = float(
        EveMarketContract.objects.filter(
            location_id__in=location_pks,
            status="outstanding",
        ).aggregate(
            total=Coalesce(
                Sum("price"),
                Value(
                    0,
                    output_field=DecimalField(max_digits=32, decimal_places=2),
                ),
            )
        )[
            "total"
        ]
        or 0
    )
    sell_line_value = F("price") * F("quantity")
    sell_orders_isk = float(
        EveMarketItemOrder.objects.filter(
            location_id__in=location_pks,
            is_buy_order=False,
        )
        .annotate(
            line_value=sell_line_value,
        )
        .aggregate(
            total=Coalesce(
                Sum(
                    "line_value",
                    output_field=DecimalField(max_digits=32, decimal_places=2),
                ),
                Value(
                    0,
                    output_field=DecimalField(max_digits=32, decimal_places=2),
                ),
            ),
        )["total"]
        or 0
    )
    total_isk_on_market = contracts_isk + sell_orders_isk

    return {
        "synced_at": timezone.now().isoformat(),
        "contracts_synced_at": (
            latest_contract.isoformat() if latest_contract else None
        ),
        "orders_synced_at": (
            latest_order.isoformat() if latest_order else None
        ),
        "understocked_contracts": understocked_contracts[:50],
        "sell_gaps": sell_gaps[:100],
        "summary": {
            "understocked_contracts": min(len(understocked_contracts), 50),
            "sell_gaps": min(len(sell_gaps), 100),
            "contracts_health_pct": contracts_health_pct,
            "sell_orders_health_pct": sell_orders_health_pct,
            "sell_orders_viability_pct": sell_orders_viability_pct,
            "overall_health_pct": overall_health_pct,
            "contract_targets": contract_targets,
            "contract_fulfilled": contract_fulfilled,
            "sell_order_targets": sell_targets,
            "sell_order_fulfilled": sell_fulfilled,
            "sell_order_viable_fulfilled": sell_viable_fulfilled,
            "contracts_isk": round(contracts_isk, 2),
            "sell_orders_isk": round(sell_orders_isk, 2),
            "total_isk_on_market": round(total_isk_on_market, 2),
        },
    }


def _health_pct(fill_ratios: list[float]) -> float | None:
    if not fill_ratios:
        return None
    return round(100.0 * sum(fill_ratios) / len(fill_ratios), 1)


def _combined_health(
    contracts_pct: float | None, sell_orders_pct: float | None
) -> float | None:
    parts = [p for p in (contracts_pct, sell_orders_pct) if p is not None]
    if not parts:
        return None
    return round(sum(parts) / len(parts), 1)
