"""Sell-order staging supply health."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.db.models import (
    DecimalField,
    F,
    Max,
    Min,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from eveuniverse.models import EveType

from market.helpers.health_common import (
    CRITICAL_RATIO,
    VOLUME_DAYS_1,
    VOLUME_DAYS_3,
    VOLUME_DAYS_7,
    VOLUME_DAYS_30,
    VOLUME_DAYS_90,
    summary_fields,
    days_of_stock,
    forge_baseline_by_type,
    health_pct,
    market_active_locations,
    sell_gap_flags,
    windowed_quantity_sum,
)
from market.helpers.item_classification import (
    ITEM_TYPE_OTHER,
    ITEM_VARIANT_OTHER,
    classify_items,
)
from market.helpers.item_ships import item_ships_by_location
from market.helpers.price_viability import is_price_viable
from market.helpers.readiness import shortfall
from market.models import EveMarketInferredSale
from market.models.item import (
    EveMarketItemOrder,
    get_effective_item_expectations_bulk,
)


def build_sell_order_health(  # noqa: C901
    *, location_id: int | None = None
) -> dict:
    """
    Sell-order staging supply health for one or all market-active locations.
    """
    locations = market_active_locations(location_id)
    if not locations:
        return {"by_location": {}}

    location_pks = [loc.pk for loc in locations]
    location_by_pk = {loc.pk: loc for loc in locations}

    now = timezone.now()
    since_1 = now - timedelta(days=VOLUME_DAYS_1)
    since_3 = now - timedelta(days=VOLUME_DAYS_3)
    since_7 = now - timedelta(days=VOLUME_DAYS_7)
    since_30 = now - timedelta(days=VOLUME_DAYS_30)
    since_90 = now - timedelta(days=VOLUME_DAYS_90)

    effective = get_effective_item_expectations_bulk(locations)
    ships_by_item = item_ships_by_location(locations)
    rows = []
    all_names = set()
    for name_map in effective.values():
        all_names.update(name_map.keys())
    type_by_name = {
        t.name: t for t in EveType.objects.filter(name__in=all_names)
    }
    target_type_ids = [t.id for t in type_by_name.values()]
    baseline_by_type = forge_baseline_by_type(target_type_ids)
    stock_by_loc_item: dict[tuple[int, int], int] = {}
    viable_by_loc_item: dict[tuple[int, int], int] = {}
    listed_value_by_loc_item: dict[tuple[int, int], float] = {}
    for order in EveMarketItemOrder.objects.filter(
        location_id__in=location_pks,
        is_buy_order=False,
        item_id__in=target_type_ids,
    ).values("location_id", "item_id", "price", "quantity"):
        key = (order["location_id"], order["item_id"])
        quantity = order["quantity"] or 0
        stock_by_loc_item[key] = stock_by_loc_item.get(key, 0) + quantity
        listed_value_by_loc_item[key] = (
            listed_value_by_loc_item.get(key, 0.0)
            + float(order["price"]) * quantity
        )
        if is_price_viable(
            order["price"], baseline_by_type.get(order["item_id"])
        ):
            viable_by_loc_item[key] = viable_by_loc_item.get(key, 0) + quantity

    classified_by_id = classify_items(target_type_ids)

    units_1d_by_loc_item: dict[tuple[int, int], int] = {}
    units_3d_by_loc_item: dict[tuple[int, int], int] = {}
    weekly_units_by_loc_item: dict[tuple[int, int], int] = {}
    units_30d_by_loc_item: dict[tuple[int, int], int] = {}
    units_90d_by_loc_item: dict[tuple[int, int], int] = {}
    sales_history_days = 0
    if target_type_ids:

        def _windowed_sum(since):
            return windowed_quantity_sum(since)

        sales_aggregates = (
            EveMarketInferredSale.objects.filter(
                location_id__in=location_pks,
                item_id__in=target_type_ids,
                inferred_at__gte=since_90,
            )
            .values("location_id", "item_id")
            .annotate(
                units_1d=_windowed_sum(since_1),
                units_3d=_windowed_sum(since_3),
                units_7d=_windowed_sum(since_7),
                units_30d=_windowed_sum(since_30),
                units_90d=Coalesce(Sum("quantity"), 0),
            )
        )
        for row in sales_aggregates:
            key = (row["location_id"], row["item_id"])
            units_1d_by_loc_item[key] = row["units_1d"]
            units_3d_by_loc_item[key] = row["units_3d"]
            weekly_units_by_loc_item[key] = row["units_7d"]
            units_30d_by_loc_item[key] = row["units_30d"]
            units_90d_by_loc_item[key] = row["units_90d"]

        earliest_sale = EveMarketInferredSale.objects.filter(
            location_id__in=location_pks,
            inferred_at__gte=since_90,
        ).aggregate(earliest=Min("inferred_at"))["earliest"]
        if earliest_sale is not None:
            sales_history_days = max(
                1, int((now - earliest_sale).total_seconds() // 86400) + 1
            )

    sell_fill_ratios_by_loc: dict[int, list[float]] = defaultdict(list)
    sell_viable_fill_ratios_by_loc: dict[int, list[float]] = defaultdict(list)
    sell_targets_by_loc: dict[int, int] = defaultdict(int)
    sell_listed_by_loc: dict[int, int] = defaultdict(int)
    sell_fulfilled_by_loc: dict[int, int] = defaultdict(int)
    sell_viable_fulfilled_by_loc: dict[int, int] = defaultdict(int)
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
            sell_targets_by_loc[loc_pk] += 1
            sell_ratio = min(1.0, current / desired)
            sell_fill_ratios_by_loc[loc_pk].append(sell_ratio)
            if current >= desired:
                sell_fulfilled_by_loc[loc_pk] += 1
            # Viability = price quality of what is listed, not empty shelves.
            if current > 0:
                sell_viable_ratio = min(1.0, viable / current)
                sell_viable_fill_ratios_by_loc[loc_pk].append(
                    sell_viable_ratio
                )
                sell_listed_by_loc[loc_pk] += 1
                if viable >= current:
                    sell_viable_fulfilled_by_loc[loc_pk] += 1
            coverage_gap = current < desired * CRITICAL_RATIO
            viability_gap = viable < desired * CRITICAL_RATIO
            avg_markup_pct = None
            if current > 0:
                baseline = baseline_by_type.get(eve_type.id)
                if baseline is not None and baseline > 0:
                    avg_price = (
                        listed_value_by_loc_item.get(
                            (loc_pk, eve_type.id), 0.0
                        )
                        / current
                    )
                    avg_markup_pct = round(
                        (avg_price / float(baseline) - 1.0) * 100.0, 1
                    )
            weekly_units = weekly_units_by_loc_item.get(
                (loc_pk, eve_type.id), 0
            )
            days_remaining = days_of_stock(current, weekly_units)
            rows.append(
                {
                    "location_id": loc.location_id,
                    "location_name": loc.location_name,
                    "short_name": loc.short_name or "",
                    "type_id": eve_type.id,
                    "item_name": name,
                    "current_quantity": current,
                    "viable_quantity": viable,
                    "expected_quantity": desired,
                    "shortfall": shortfall(viable, desired),
                    "coverage_gap": coverage_gap,
                    "viability_gap": viability_gap,
                    "item_type": (
                        classified_by_id[eve_type.id].item_type
                        if eve_type.id in classified_by_id
                        else ITEM_TYPE_OTHER
                    ),
                    "item_variant": (
                        classified_by_id[eve_type.id].item_variant
                        if eve_type.id in classified_by_id
                        else ITEM_VARIANT_OTHER
                    ),
                    "units_1d": units_1d_by_loc_item.get(
                        (loc_pk, eve_type.id), 0
                    ),
                    "units_3d": units_3d_by_loc_item.get(
                        (loc_pk, eve_type.id), 0
                    ),
                    "weekly_units": weekly_units,
                    "units_30d": units_30d_by_loc_item.get(
                        (loc_pk, eve_type.id), 0
                    ),
                    "units_90d": units_90d_by_loc_item.get(
                        (loc_pk, eve_type.id), 0
                    ),
                    "avg_markup_pct": avg_markup_pct,
                    "days_of_stock": days_remaining,
                    "flags": sell_gap_flags(
                        current, desired, avg_markup_pct, days_remaining
                    ),
                    "ships": ships_by_item.get(loc_pk, {}).get(name, []),
                }
            )

    rows.sort(key=lambda row: (-row["shortfall"], row["item_name"]))

    latest_order_by_loc = dict(
        EveMarketItemOrder.objects.filter(location_id__in=location_pks)
        .values("location_id")
        .annotate(latest=Max("created_at"))
        .values_list("location_id", "latest")
    )

    isk_decimal_field = DecimalField(max_digits=32, decimal_places=2)
    sell_line_value = F("price") * F("quantity")
    sell_orders_isk_by_loc = {
        row["location_id"]: float(row["total"] or 0)
        for row in EveMarketItemOrder.objects.filter(
            location_id__in=location_pks,
            is_buy_order=False,
        )
        .annotate(line_value=sell_line_value)
        .values("location_id")
        .annotate(
            total=Coalesce(
                Sum("line_value", output_field=isk_decimal_field),
                Value(0, output_field=isk_decimal_field),
            )
        )
    }

    by_location: dict[int, dict] = {}
    for loc in locations:
        loc_pk = loc.pk
        loc_rows = [
            row for row in rows if row["location_id"] == loc.location_id
        ]
        loc_latest_order = latest_order_by_loc.get(loc_pk)
        by_location[loc.location_id] = {
            "synced_at": (
                loc_latest_order.isoformat() if loc_latest_order else None
            ),
            "rows": loc_rows,
            "summary": {
                "health_pct": health_pct(
                    sell_fill_ratios_by_loc.get(loc_pk, [])
                ),
                "viability_pct": health_pct(
                    sell_viable_fill_ratios_by_loc.get(loc_pk, [])
                ),
                "targets": sell_targets_by_loc.get(loc_pk, 0),
                "listed_targets": sell_listed_by_loc.get(loc_pk, 0),
                "fulfilled": sell_fulfilled_by_loc.get(loc_pk, 0),
                "viable_fulfilled": sell_viable_fulfilled_by_loc.get(
                    loc_pk, 0
                ),
                "isk": round(sell_orders_isk_by_loc.get(loc_pk, 0.0), 2),
                "history_days": sales_history_days,
            },
        }

    return {"by_location": by_location}


def get_live_sell_order_supply(*, location_id: int) -> dict | None:
    payload = build_sell_order_health(location_id=location_id)[
        "by_location"
    ].get(location_id)
    if payload is None:
        return None
    return {
        "location_id": location_id,
        **summary_fields(
            {
                **payload["summary"],
                "synced_at": payload.get("synced_at"),
            }
        ),
        "rows": payload["rows"],
    }
