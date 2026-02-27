from ninja import Router
from pydantic import BaseModel

from django.db.models import Min, Sum

from eveonline.models import EveLocation
from eveuniverse.models import EveType
from market.models.contract import EveMarketContractExpectation
from market.models.item import (
    EveMarketFittingExpectation,
    EveMarketItemExpectation,
    EveMarketItemOrder,
    get_effective_item_expectations,
)

router = Router(tags=["Market"])


def _get_baseline_prices() -> dict[str, float]:
    """Lowest sell-order price per item at the price_baseline location."""
    baseline = EveLocation.objects.filter(price_baseline=True).first()
    if not baseline:
        return {}
    return dict(
        EveMarketItemOrder.objects.filter(location=baseline)
        .values("item__name")
        .annotate(lowest=Min("price"))
        .values_list("item__name", "lowest")
    )


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
    lowest_price: float | None
    baseline_price: float | None


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
                    lowest_price=float(lp) if lp is not None else None,
                    baseline_price=float(bp) if bp is not None else None,
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
