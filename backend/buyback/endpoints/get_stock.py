"""GET /stock – on-hand buyback hangar quantities."""

from ninja import Router
from eveuniverse.models import EveType

from buyback.endpoints.schemas import BuybackOnHandItem, BuybackOnHandResponse
from buyback.helpers.remaining import available_stock_quantities
from buyback.helpers.valuation import batch_estimate_guide_isk
from buyback.models import BuybackAcceptedItem, BuybackHangarSnapshot

router = Router(tags=["Buyback"])


@router.get(
    "/stock",
    description="Available hangar quantities, minus pending purchase reservations.",
    response=BuybackOnHandResponse,
)
def get_stock(request):
    accepted = {
        item.eve_type_id: item
        for item in BuybackAcceptedItem.objects.filter(
            active=True
        ).select_related("eve_type")
    }
    snapshot = BuybackHangarSnapshot.objects.order_by("-taken_at").first()
    updated_at = None
    if snapshot is not None:
        updated_at = snapshot.taken_at.isoformat()
    else:
        for item in accepted.values():
            if item.metrics_updated_at and (
                updated_at is None
                or item.metrics_updated_at.isoformat() > updated_at
            ):
                updated_at = item.metrics_updated_at.isoformat()
    quantities = available_stock_quantities()

    rows: list[tuple[int, str, int, str | None, str | None]] = []
    for type_id, qty in sorted(
        quantities.items(),
        key=lambda pair: (
            accepted[pair[0]].eve_type.name
            if pair[0] in accepted
            else str(pair[0])
        ),
    ):
        if qty <= 0:
            continue
        item = accepted.get(type_id)
        if item is not None:
            rows.append(
                (
                    type_id,
                    item.eve_type.name,
                    qty,
                    item.category,
                    item.demand_status,
                )
            )
            continue
        eve_type = EveType.objects.filter(id=type_id).first()
        if eve_type is None:
            continue
        rows.append((type_id, eve_type.name, qty, None, None))

    isk_values = batch_estimate_guide_isk(
        [(type_id, name, qty) for type_id, name, qty, _, _ in rows]
    )

    items = [
        BuybackOnHandItem(
            type_id=type_id,
            name=name,
            category=category,
            quantity=qty,
            demand_status=demand_status,
            isk_value=isk_value,
        )
        for (type_id, name, qty, category, demand_status), isk_value in zip(
            rows, isk_values
        )
    ]

    return BuybackOnHandResponse(items=items, updated_at=updated_at)
