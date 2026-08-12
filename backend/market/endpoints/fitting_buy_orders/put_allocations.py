"""PUT /fitting-buy-orders/{order_id}/allocations — split a short buy across variants."""

from ninja import Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from market.endpoints.fitting_buy_orders.common import (
    get_order_or_404,
    require_owner,
)
from market.helpers.fitting_buy_allocations import (
    AllocationError,
    set_allocations,
)
from market.helpers.fitting_buy_serialize import (
    FittingBuyOrderDetailSchema,
    serialize_order_detail,
)

PATH = "/fitting-buy-orders/{order_id}/allocations"
METHOD = "put"
ROUTE_SPEC = {
    "response": {
        200: FittingBuyOrderDetailSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Split a short module's buy qty across original and variants",
}


class AllocationEntrySchema(Schema):
    type_id: int
    qty: int


class PutAllocationsRequest(Schema):
    preferred_type_id: int
    entries: list[AllocationEntrySchema]


def put_fitting_buy_allocations(
    request, order_id: int, payload: PutAllocationsRequest
):
    order, err = get_order_or_404(order_id)
    if err:
        return err
    denied = require_owner(request, order)
    if denied:
        return denied

    try:
        set_allocations(
            order,
            preferred_type_id=payload.preferred_type_id,
            entries=[
                {"type_id": entry.type_id, "qty": entry.qty}
                for entry in payload.entries
            ],
        )
    except AllocationError as exc:
        return 400, ErrorResponse(detail=str(exc))

    return serialize_order_detail(order, request.user)
