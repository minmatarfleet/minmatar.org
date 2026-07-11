from collections import defaultdict

from django.db.models import Max, Sum
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

    current_by_type = {
        row["item_id"]: row["total"]
        for row in EveMarketItemOrder.objects.filter(
            location=location, is_buy_order=True, item_id__in=type_ids
        )
        .values("item_id")
        .annotate(total=Sum("quantity"))
    }
    highest_buy_by_type = {
        row["item_id"]: row["price"]
        for row in EveMarketItemOrder.objects.filter(
            location=location, is_buy_order=True, item_id__in=type_ids
        )
        .values("item_id")
        .annotate(price=Max("price"))
    }
    issuers_by_type = defaultdict(set)
    for row in EveMarketItemOrder.objects.filter(
        location=location,
        is_buy_order=True,
        item_id__in=type_ids,
        issuer_external_id__isnull=False,
    ).values("item_id", "issuer_external_id"):
        issuers_by_type[row["item_id"]].add(row["issuer_external_id"])

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
