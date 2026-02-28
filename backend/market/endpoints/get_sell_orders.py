from ninja import Router
from pydantic import BaseModel

from django.db.models import Min, OuterRef, Subquery, Sum

from eveonline.models import EveLocation
from eveuniverse.models import EveType

from market.endpoints.cache import get_cached
from market.models import EveMarketItemLocationPrice
from market.models.contract import EveMarketContractExpectation
from market.models.history import EveMarketItemHistory
from market.models.item import (
    EveMarketFittingExpectation,
    EveMarketItemExpectation,
    EveMarketItemOrder,
    get_effective_item_expectations,
)

router = Router(tags=["Market"])


def _get_baseline_prices() -> dict[str, float]:
    """Latest market history average price per item in the price_baseline location's region."""
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    if not baseline or not baseline.region_id:
        return {}
    latest_date = (
        EveMarketItemHistory.objects.filter(
            region_id=baseline.region_id,
            item_id=OuterRef("item_id"),
        )
        .order_by("-date")
        .values("date")[:1]
    )
    return dict(
        EveMarketItemHistory.objects.filter(
            region_id=baseline.region_id,
            date=Subquery(latest_date),
        ).values_list("item__name", "average")
    )


def _get_baseline_location_prices() -> (
    dict[str, tuple[float | None, float | None, float | None]]
):
    """Sell, buy, split prices per item name at the price_baseline location (EveMarketItemLocationPrice)."""
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    if not baseline:
        return {}
    rows = (
        EveMarketItemLocationPrice.objects.filter(location=baseline)
        .select_related("item")
        .values_list("item__name", "sell_price", "buy_price", "split_price")
    )
    return {
        name: (
            float(sell) if sell is not None else None,
            float(buy) if buy is not None else None,
            float(split) if split is not None else None,
        )
        for name, sell, buy, split in rows
    }


class SellOrderItemResponse(BaseModel):
    item_name: str
    type_id: int | None
    category_id: int | None
    category_name: str
    group_id: int | None
    group_name: str
    expected_quantity: int
    current_quantity: int
    fulfilled: bool
    issuer_ids: list[int]
    current_lowest_price: float | None
    baseline_price: float | None
    baseline_sell_price: float | None
    baseline_buy_price: float | None
    baseline_split_price: float | None


class SellOrderLocationResponse(BaseModel):
    location_id: int
    location_name: str
    short_name: str
    is_price_baseline: bool
    items: list[SellOrderItemResponse]


@router.get(
    "/sell-orders",
    description="Get sell order expectations and current stock per location",
    response=list[SellOrderLocationResponse],
)
@get_cached(
    key_suffix=lambda req, location_id=None: f"sell-orders:{location_id or 'all'}"
)
def get_sell_orders(request, location_id: int | None = None):
    if location_id is not None:
        locations = EveLocation.objects.filter(
            location_id=location_id, market_active=True
        )
    else:
        item_location_ids = set(
            EveMarketItemExpectation.objects.values_list(
                "location_id", flat=True
            )
        )
        fitting_location_ids = set(
            EveMarketFittingExpectation.objects.values_list(
                "location_id", flat=True
            )
        )
        contract_location_ids = set(
            EveMarketContractExpectation.objects.values_list(
                "location_id", flat=True
            )
        )
        all_ids = (
            item_location_ids | fitting_location_ids | contract_location_ids
        )
        locations = EveLocation.objects.filter(
            location_id__in=all_ids, market_active=True
        ).order_by("location_name")

    baseline_prices = _get_baseline_prices()
    baseline_location_prices = _get_baseline_location_prices()

    results = []
    for location in locations:
        effective = get_effective_item_expectations(location)

        current_stock = dict(
            EveMarketItemOrder.objects.filter(location=location)
            .values("item__name")
            .annotate(total=Sum("quantity"))
            .values_list("item__name", "total")
        )

        all_item_names = set(effective.keys()) | set(current_stock.keys())

        type_info = dict(
            (row[0], (row[1], row[2], row[3] or "", row[4], row[5] or ""))
            for row in EveType.objects.filter(
                name__in=all_item_names
            ).values_list(
                "name",
                "id",
                "eve_group__eve_category_id",
                "eve_group__eve_category__name",
                "eve_group_id",
                "eve_group__name",
            )
        )

        lowest_prices = dict(
            EveMarketItemOrder.objects.filter(
                location=location, item__name__in=all_item_names
            )
            .values("item__name")
            .annotate(lowest=Min("price"))
            .values_list("item__name", "lowest")
        )

        order_issuers = (
            EveMarketItemOrder.objects.filter(
                location=location,
                item__name__in=all_item_names,
                issuer_external_id__isnull=False,
            )
            .distinct()
            .values_list("item__name", "issuer_external_id")
        )
        issuers_by_name: dict[str, list[int]] = {}
        for item_name, issuer_id in order_issuers:
            issuer_id_int = int(issuer_id)
            if item_name not in issuers_by_name:
                issuers_by_name[item_name] = []
            if issuer_id_int not in issuers_by_name[item_name]:
                issuers_by_name[item_name].append(issuer_id_int)

        items = []
        for name in sorted(all_item_names):
            expected = effective.get(name, 0)
            current = current_stock.get(name, 0)
            type_id, category_id, category_name, group_id, group_name = (
                type_info.get(name, (None, None, "", None, ""))
            )
            lp = lowest_prices.get(name)
            bp = baseline_prices.get(name)
            blp = baseline_location_prices.get(name)
            baseline_sell, baseline_buy, baseline_split = (
                blp if blp else (None, None, None)
            )
            items.append(
                SellOrderItemResponse(
                    item_name=name,
                    type_id=type_id,
                    category_id=category_id,
                    category_name=category_name,
                    group_id=group_id,
                    group_name=group_name,
                    expected_quantity=expected,
                    current_quantity=current,
                    fulfilled=current >= expected if expected > 0 else True,
                    issuer_ids=issuers_by_name.get(name, []),
                    current_lowest_price=float(lp) if lp is not None else None,
                    baseline_price=float(bp) if bp is not None else None,
                    baseline_sell_price=baseline_sell,
                    baseline_buy_price=baseline_buy,
                    baseline_split_price=baseline_split,
                )
            )

        results.append(
            SellOrderLocationResponse(
                location_id=location.location_id,
                location_name=location.location_name,
                short_name=location.short_name,
                is_price_baseline=location.price_baseline,
                items=items,
            )
        )

    return results
