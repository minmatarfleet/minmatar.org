from collections import defaultdict

from django.urls import reverse

from market.helpers.pricing import get_prices_by_type_id
from market.models import (
    EveMarketBuyOrderExpectation,
    EveMarketItemLocationPrice,
    EveMarketItemOrder,
)


def build_location_buy_orders_context(location) -> dict:
    expectations = list(
        EveMarketBuyOrderExpectation.objects.filter(location=location)
        .select_related("item")
        .order_by("item__name")
    )
    type_ids = [exp.item_id for exp in expectations]

    current_by_type: dict[int, int] = defaultdict(int)
    highest_buy_by_type: dict[int, int] = {}
    issuers_by_type: dict[int, set] = defaultdict(set)
    for row in EveMarketItemOrder.objects.filter(
        location=location, is_buy_order=True, item_id__in=type_ids
    ).values("item_id", "price", "quantity", "issuer_external_id"):
        item_id = row["item_id"]
        current_by_type[item_id] += row["quantity"]
        price = int(row["price"])
        if (
            item_id not in highest_buy_by_type
            or price > highest_buy_by_type[item_id]
        ):
            highest_buy_by_type[item_id] = price
        issuer_id = row["issuer_external_id"]
        if issuer_id is not None:
            issuers_by_type[item_id].add(issuer_id)

    location_prices = {
        row.item_id: row
        for row in EveMarketItemLocationPrice.objects.filter(
            location=location, item_id__in=type_ids
        )
    }
    jita_prices = get_prices_by_type_id(type_ids) if type_ids else {}

    rows = []
    for exp in expectations:
        item = exp.item
        loc_price = location_prices.get(item.pk)
        history_url = (
            reverse("admin:market_evemarketitemhistory_changelist")
            + f"?item__id__exact={item.pk}"
        )
        rows.append(
            {
                "expectation": exp,
                "item_name": item.name,
                "expected_qty": exp.quantity,
                "current_qty": current_by_type.get(item.pk, 0),
                "highest_buy": highest_buy_by_type.get(item.pk),
                "location_buy": loc_price.buy_price if loc_price else None,
                "location_sell": loc_price.sell_price if loc_price else None,
                "jita_price": jita_prices.get(item.pk),
                "issuers": sorted(issuers_by_type.get(item.pk, set())),
                "edit_url": reverse(
                    "admin:market_evemarketbuyorderexpectation_change",
                    args=[exp.pk],
                ),
                "history_url": history_url,
            }
        )

    return {
        "rows": rows,
        "add_url": (
            reverse("admin:market_evemarketbuyorderexpectation_add")
            + f"?location={location.pk}"
        ),
    }
