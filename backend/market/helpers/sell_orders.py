from collections import defaultdict

from django.contrib import admin
from django.contrib.admin.views.main import PAGE_VAR, SEARCH_VAR
from django.urls import reverse
from django.utils.http import urlencode

from eveuniverse.models import EveType
from fittings.models import EveFittingRefit

from market.helpers.sell_orders_changelist import (
    LocationSellOrdersChangeList,
    LocationSellOrdersModelAdmin,
    SellOrderMarkupListFilter,
    SellOrderSourceListFilter,
    SellOrderStockListFilter,
)
from market.helpers.pricing import (
    get_prices_by_type_id,
    get_volume_90d_by_type_id,
)
from market.helpers.qualification import get_qualified_sell_fittings
from market.models import (
    EveMarketContractExpectation,
    EveMarketFittingExpectation,
    EveMarketItemExpectation,
    EveMarketItemLocationPrice,
    EveMarketItemOrder,
)
from market.models.item import (
    _get_consumable_items,
    get_effective_item_expectations,
    parse_eft_items,
)

SOURCE_REFIT = "refit"
SOURCE_CONSUMABLE = "consumable"
SOURCE_NON_DOCTRINE_SHIP = "non-doctrine ship"

# Stock bands use desired_qty as target.
STOCK_VERY_UNDERSTOCKED_MAX_RATIO = 0.25
STOCK_UNDERSTOCKED_MAX_RATIO = 0.50
STOCK_OVERSTOCKED_MAX_RATIO = 2.0

MARKUP_VERY_UNDERPRICED_MAX = -20
MARKUP_UNDERPRICED_MAX = -5
MARKUP_NORMAL_MAX = 5
MARKUP_OVERPRICED_MAX = 20

# Listed-within-reason: exclude sell orders priced >20% above Jita when
# computing actionable stock. Cheap items (Jita sell < 1M ISK) always count.
REASONABLE_MARKUP_MAX_PCT = 20
REASONABLE_JITA_PRICE_FLOOR = 1_000_000


def _order_quantity_counts_as_reasonable(
    order_price,
    jita_sell_price: int | None,
) -> bool:
    """Return True if this sell order counts toward within-reason listed stock."""
    if jita_sell_price is None or jita_sell_price <= 0:
        return True
    if jita_sell_price < REASONABLE_JITA_PRICE_FLOOR:
        return True
    price = int(order_price)
    max_reasonable = jita_sell_price * (100 + REASONABLE_MARKUP_MAX_PCT) // 100
    return price <= max_reasonable


def _aggregate_order_rows(
    order_rows: list[dict],
    jita_sell_by_type: dict[int, int],
) -> tuple[
    set[int],
    dict[int, int],
    dict[int, int],
    dict[int, int],
    dict[int, object],
]:
    """Aggregate pre-fetched sell order rows in one Python pass."""
    type_ids: set[int] = set()
    total_by_type: dict[int, int] = defaultdict(int)
    reasonable_by_type: dict[int, int] = defaultdict(int)
    min_price_by_type: dict[int, int] = {}
    last_synced_by_type: dict[int, object] = {}

    for order in order_rows:
        item_id = order["item_id"]
        quantity = order["quantity"]
        price = order["price"]
        created_at = order["created_at"]
        type_ids.add(item_id)
        total_by_type[item_id] += quantity
        if _order_quantity_counts_as_reasonable(
            price, jita_sell_by_type.get(item_id)
        ):
            reasonable_by_type[item_id] += quantity
        price_int = int(price)
        if (
            item_id not in min_price_by_type
            or price_int < min_price_by_type[item_id]
        ):
            min_price_by_type[item_id] = price_int
        if (
            item_id not in last_synced_by_type
            or created_at > last_synced_by_type[item_id]
        ):
            last_synced_by_type[item_id] = created_at

    return (
        type_ids,
        dict(total_by_type),
        dict(reasonable_by_type),
        min_price_by_type,
        last_synced_by_type,
    )


def _fetch_sell_order_stats(
    location,
    jita_sell_by_type: dict[int, int],
) -> tuple[
    set[int],
    dict[int, int],
    dict[int, int],
    dict[int, int],
    dict[int, object],
]:
    """Fetch sell orders for a location and aggregate in one DB round-trip."""
    order_rows = list(
        _sell_orders_queryset(location).values(
            "item_id", "price", "quantity", "created_at"
        )
    )
    return _aggregate_order_rows(order_rows, jita_sell_by_type)


def _fitting_ship_name(eft_format: str) -> str | None:
    """Ship hull name from the first line of an EFT fitting string."""
    lines = eft_format.strip().split("\n")
    if not lines:
        return None
    header = lines[0].strip()
    ship_name = header.split(",")[0].strip().strip("[]")
    return ship_name or None


def _stock_level(row: dict) -> str | None:
    current = row.get("reasonable_qty")
    if current is None:
        current = row.get("current_qty") or 0
    target = row.get("desired_qty") or 0
    if target <= 0:
        return None
    if current == 0:
        return "no_stock"
    ratio = current / target
    if ratio < STOCK_VERY_UNDERSTOCKED_MAX_RATIO:
        return "very_understocked"
    if ratio < STOCK_UNDERSTOCKED_MAX_RATIO:
        return "understocked"
    if ratio > STOCK_OVERSTOCKED_MAX_RATIO:
        return "very_overstocked"
    if ratio > 1:
        return "overstocked"
    return None


def _markup_level(row: dict) -> str | None:
    markup = row.get("markup_pct")
    if markup is None:
        return None
    if markup < MARKUP_VERY_UNDERPRICED_MAX:
        return "very_underpriced"
    if markup < MARKUP_UNDERPRICED_MAX:
        return "underpriced"
    if markup <= MARKUP_NORMAL_MAX:
        return "normal"
    if markup <= MARKUP_OVERPRICED_MAX:
        return "overpriced"
    return "very_overpriced"


def _is_unreferenced_row(row: dict) -> bool:
    return not row.get("references") and not row.get("sources")


def _format_reference_display(
    reference_names: list[str],
) -> tuple[str, str, list[str]]:
    """Return (cell text, hover tooltip, names) for the References column."""
    if not reference_names:
        return "", "", []
    count = len(reference_names)
    return f"{count} ship fits", "\n".join(reference_names), reference_names


def _calculate_markup_pct(
    list_price: int | None, jita_sell_price: int | None
) -> int | None:
    if not list_price or not jita_sell_price or jita_sell_price <= 0:
        return None
    return round((list_price - jita_sell_price) / jita_sell_price * 100)


def _resolve_list_price(
    type_id: int | None,
    lowest_sell_by_type: dict[int, int],
    location_sell_by_type: dict[int, int],
) -> int | None:
    if not type_id:
        return None
    if type_id in lowest_sell_by_type:
        return lowest_sell_by_type[type_id]
    return location_sell_by_type.get(type_id)


def _new_row(item_name: str) -> dict:
    return {
        "item_name": item_name,
        "current_qty": 0,
        "reasonable_qty": 0,
        "desired_qty": 0,
        "recommended_qty": 0,
        "references": set(),
        "sources": set(),
    }


def get_sell_order_recommendations(location) -> list[dict]:
    """Consumables and refit modules scaled by contract expectation quantity."""
    recommendations = []
    seen = set()

    contract_expectations = list(
        EveMarketContractExpectation.objects.filter(location=location)
        .select_related("fitting")
        .order_by("fitting__name")
    )
    fitting_ids = [cexp.fitting_id for cexp in contract_expectations]
    refits_by_fitting: dict[int, list] = defaultdict(list)
    for refit in EveFittingRefit.objects.filter(
        base_fitting_id__in=fitting_ids
    ).order_by("name"):
        refits_by_fitting[refit.base_fitting_id].append(refit)

    for cexp in contract_expectations:
        fitting = cexp.fitting
        contract_qty = cexp.quantity
        for item_name, qty in _get_consumable_items(fitting).items():
            key = ("consumable", item_name, fitting.pk)
            if key in seen:
                continue
            seen.add(key)
            recommendations.append(
                {
                    "item_name": item_name,
                    "quantity": qty * contract_qty,
                    "fitting_name": fitting.name,
                    "source": fitting.name,
                    "kind": "consumable",
                }
            )
        for refit in refits_by_fitting.get(fitting.pk, []):
            for item_name, qty in parse_eft_items(refit.eft_format).items():
                key = ("refit", item_name, refit.pk, fitting.pk)
                if key in seen:
                    continue
                seen.add(key)
                recommendations.append(
                    {
                        "item_name": item_name,
                        "quantity": qty * contract_qty,
                        "fitting_name": fitting.name,
                        "source": f"{fitting.name} refit: {refit.name}",
                        "kind": "refit",
                    }
                )

    recommendations.sort(
        key=lambda row: (row["item_name"].lower(), row["source"])
    )
    return recommendations


def _sell_orders_queryset(location):
    return EveMarketItemOrder.objects.filter(
        location=location,
        is_buy_order=False,
    )


def save_sell_order_desired_quantities(
    location, post_data, allowed_ids: set[int] | None = None
) -> int:
    """Persist desired quantities as pinned item expectations. Returns rows saved."""
    updated = 0
    prefix = "desired_"
    for key, raw_value in post_data.items():
        if not key.startswith(prefix):
            continue
        type_id = int(key.removeprefix(prefix))
        if allowed_ids is not None and type_id not in allowed_ids:
            continue
        if raw_value in (None, ""):
            continue
        quantity = int(raw_value)
        if quantity <= 0:
            deleted, _ = EveMarketItemExpectation.objects.filter(
                location=location,
                item_id=type_id,
            ).delete()
            if deleted:
                updated += 1
            continue
        EveMarketItemExpectation.objects.update_or_create(
            location=location,
            item_id=type_id,
            defaults={"quantity": quantity},
        )
        updated += 1
    return updated


def build_unified_sell_order_rows(location) -> list[dict]:  # noqa: C901
    """Merge expectations, doctrine recommendations, and live stock into one table."""
    rows_by_name: dict[str, dict] = {}

    def row_for(item_name: str) -> dict:
        if item_name not in rows_by_name:
            rows_by_name[item_name] = _new_row(item_name)
        return rows_by_name[item_name]

    pinned: dict[str, int] = {}
    pinned_expectations = {}
    for exp in EveMarketItemExpectation.objects.filter(
        location=location
    ).select_related("item"):
        pinned[exp.item.name] = exp.quantity
        pinned_expectations[exp.item_id] = exp.pk
    pinned_names = set(pinned.keys())

    for fexp in EveMarketFittingExpectation.objects.filter(
        location=location
    ).select_related("fitting"):
        ship_name = _fitting_ship_name(fexp.fitting.eft_format)
        for item_name, qty in fexp.get_item_quantities().items():
            if item_name in pinned_names:
                continue
            row = row_for(item_name)
            row["desired_qty"] = max(row["desired_qty"], qty)
            row["references"].add(fexp.fitting.name)
            if item_name == ship_name:
                row["sources"].add(SOURCE_NON_DOCTRINE_SHIP)
            else:
                row["sources"].add("fitting")

    for cexp in EveMarketContractExpectation.objects.filter(
        location=location
    ).select_related("fitting"):
        for item_name, qty in _get_consumable_items(cexp.fitting).items():
            if item_name in pinned_names:
                continue
            total = qty * cexp.quantity
            row = row_for(item_name)
            row["desired_qty"] = max(row["desired_qty"], total)
            row["references"].add(cexp.fitting.name)
            row["sources"].add("contract consumable")

    for item_name, qty in pinned.items():
        row = row_for(item_name)
        row["desired_qty"] = qty
        row["sources"].add("pinned")

    for rec in get_sell_order_recommendations(location):
        row = row_for(rec["item_name"])
        row["recommended_qty"] += rec["quantity"]
        row["references"].add(rec["fitting_name"])
        row["sources"].add(rec["kind"])

    order_rows = list(
        _sell_orders_queryset(location).values(
            "item_id", "price", "quantity", "created_at"
        )
    )
    order_type_ids = {row["item_id"] for row in order_rows}
    jita_for_orders = (
        get_prices_by_type_id(list(order_type_ids)) if order_type_ids else {}
    )
    (
        _,
        current_by_type,
        reasonable_by_type,
        lowest_sell_by_type,
        last_synced_by_type,
    ) = _aggregate_order_rows(order_rows, jita_for_orders)
    type_names_by_id = dict(
        EveType.objects.filter(pk__in=current_by_type.keys()).values_list(
            "pk", "name"
        )
    )
    for type_id, current_qty in current_by_type.items():
        item_name = type_names_by_id.get(type_id)
        if not item_name:
            continue
        row = row_for(item_name)
        row["current_qty"] = current_qty
        row["reasonable_qty"] = reasonable_by_type.get(type_id, 0)

    effective = get_effective_item_expectations(location)
    type_ids_by_name = dict(
        EveType.objects.filter(name__in=rows_by_name.keys()).values_list(
            "name", "pk"
        )
    )
    all_type_ids = [tid for tid in type_ids_by_name.values() if tid]
    extra_type_ids = [
        tid for tid in all_type_ids if tid not in jita_for_orders
    ]
    jita_sell_by_type = {
        **jita_for_orders,
        **(get_prices_by_type_id(extra_type_ids) if extra_type_ids else {}),
    }
    location_sell_by_type = {
        row.item_id: row.sell_price
        for row in EveMarketItemLocationPrice.objects.filter(
            location=location, item_id__in=all_type_ids
        )
        if row.sell_price is not None
    }
    volume_90d_by_type = (
        get_volume_90d_by_type_id(all_type_ids) if all_type_ids else {}
    )

    unified_rows = []
    for item_name in sorted(rows_by_name.keys(), key=str.lower):
        row = rows_by_name[item_name]
        if (
            row["desired_qty"] == 0
            and row["recommended_qty"] == 0
            and row["current_qty"] == 0
            and item_name not in effective
        ):
            continue
        type_id = type_ids_by_name.get(item_name)
        list_price = _resolve_list_price(
            type_id, lowest_sell_by_type, location_sell_by_type
        )
        jita_sell_price = jita_sell_by_type.get(type_id) if type_id else None
        markup_pct = _calculate_markup_pct(list_price, jita_sell_price)
        volume_90d = volume_90d_by_type.get(type_id) if type_id else None
        reference_names = sorted(row["references"], key=str.lower)
        references_display, references_tooltip, references_names = (
            _format_reference_display(reference_names)
        )
        unified_rows.append(
            {
                "item_name": item_name,
                "type_id": type_id,
                "current_qty": row["current_qty"],
                "reasonable_qty": row.get(
                    "reasonable_qty", row["current_qty"]
                ),
                "desired_qty": effective.get(item_name, row["desired_qty"]),
                "recommended_qty": row["recommended_qty"],
                "list_price": list_price,
                "jita_sell_price": jita_sell_price,
                "markup_pct": markup_pct,
                "volume_90d": volume_90d,
                "references": ", ".join(reference_names),
                "references_display": references_display,
                "references_tooltip": references_tooltip,
                "references_names": references_names,
                "sources": ", ".join(sorted(row["sources"], key=str.lower)),
                "is_pinned": item_name in pinned_names,
                "is_editable": type_id is not None,
                "pinned_expectation_id": pinned_expectations.get(type_id),
                "last_synced_at": last_synced_by_type.get(type_id),
            }
        )
    return unified_rows


def filter_sell_order_rows(
    rows: list[dict],
    *,
    search: str = "",
    source_filter: str = "",
    stock_filter: str = "",
    markup_filter: str = "",
    hide_unreferenced: bool = False,
) -> list[dict]:
    filtered = rows
    if hide_unreferenced:
        filtered = [row for row in filtered if not _is_unreferenced_row(row)]
    if search:
        needle = search.casefold()
        filtered = [
            row
            for row in filtered
            if needle in row["item_name"].casefold()
            or needle in row["references"].casefold()
        ]
    if source_filter:
        filtered = [
            row
            for row in filtered
            if source_filter in row["sources"].split(", ")
        ]
    if stock_filter:
        filtered = [
            row for row in filtered if _stock_level(row) == stock_filter
        ]
    if markup_filter:
        filtered = [
            row for row in filtered if _markup_level(row) == markup_filter
        ]
    return filtered


def _sell_order_query_params(
    search: str = "",
    source_filter: str = "",
    stock_filter: str = "",
    markup_filter: str = "",
    page: int | None = None,
) -> dict[str, str]:
    params = {}
    if search:
        params[SEARCH_VAR] = search
    if source_filter:
        params[SellOrderSourceListFilter.parameter_name] = source_filter
    if stock_filter:
        params[SellOrderStockListFilter.parameter_name] = stock_filter
    if markup_filter:
        params[SellOrderMarkupListFilter.parameter_name] = markup_filter
    if page and page > 1:
        params[PAGE_VAR] = str(page)
    return params


def build_location_sell_orders_context(location, request=None) -> dict:
    """Build admin context for sell orders at a location."""
    all_rows = build_unified_sell_order_rows(location)

    search = ""
    source_filter = ""
    stock_filter = ""
    markup_filter = ""
    if request is not None:
        search = (request.GET.get(SEARCH_VAR) or "").strip()
        source_filter = (
            request.GET.get(SellOrderSourceListFilter.parameter_name) or ""
        ).strip()
        stock_filter = (
            request.GET.get(SellOrderStockListFilter.parameter_name) or ""
        ).strip()
        markup_filter = (
            request.GET.get(SellOrderMarkupListFilter.parameter_name) or ""
        ).strip()

    filtered_rows = filter_sell_order_rows(
        all_rows,
        search=search,
        source_filter=source_filter,
        stock_filter=stock_filter,
        markup_filter=markup_filter,
        hide_unreferenced=not bool(
            search or source_filter or stock_filter or markup_filter
        ),
    )
    model_admin = LocationSellOrdersModelAdmin(EveType, admin.site)
    cl = (
        LocationSellOrdersChangeList(
            request,
            model_admin=model_admin,
            filtered_rows=filtered_rows,
            total_row_count=len(all_rows),
        )
        if request is not None
        else None
    )

    base_params = _sell_order_query_params(
        search=search,
        source_filter=source_filter,
        stock_filter=stock_filter,
        markup_filter=markup_filter,
    )
    form_action = reverse(
        "admin:market_location_sell_orders", args=[location.pk]
    )
    form_action_query = urlencode(base_params)
    if form_action_query:
        form_action = f"{form_action}?{form_action_query}"

    opts = model_admin.model._meta

    return {
        "cl": cl,
        "opts": opts,
        "media": model_admin.media,
        "form_action": form_action,
        "total_row_count": len(all_rows),
        "filtered_row_count": len(filtered_rows),
        "qualified_fitting_count": len(
            list(get_qualified_sell_fittings(location))
        ),
        "manage_fitting_expectations_url": reverse(
            "admin:market_location_fitting_expectations",
            args=[location.pk],
        ),
        "manage_contract_expectations_url": reverse(
            "admin:market_location_contract_expectations",
            args=[location.pk],
        ),
    }
