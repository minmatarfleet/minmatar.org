"""POST /fitting-buy-orders — create a fitting buy order with optional lines."""

from django.db import transaction
from ninja import Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from fittings.models import EveFitting
from market.helpers.fitting_buy_check import ensure_jita_check
from market.helpers.fitting_buy_plan import sync_order_items
from market.helpers.fitting_buy_serialize import (
    FittingBuyOrderDetailSchema,
    serialize_order_detail,
)
from market.models.fitting_buy_order import (
    FittingBuyOrder,
    FittingBuyOrderLine,
)

PATH = "/fitting-buy-orders"
METHOD = "post"
ROUTE_SPEC = {
    "response": {
        201: FittingBuyOrderDetailSchema,
        400: ErrorResponse,
        401: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Create a fitting buy order",
}


class CreateFittingBuyLineRequest(Schema):
    fitting_id: int
    quantity: int = 1


class CreateFittingBuyOrderRequest(Schema):
    notes: str = ""
    include_hull: bool = False
    lines: list[CreateFittingBuyLineRequest] = []


def post_fitting_buy_order(request, payload: CreateFittingBuyOrderRequest):
    if not payload.lines:
        return 400, ErrorResponse(
            detail="Add at least one fitting before creating an order."
        )

    fitting_ids = [row.fitting_id for row in payload.lines]
    fittings = {f.id: f for f in EveFitting.objects.filter(id__in=fitting_ids)}
    missing = [fid for fid in fitting_ids if fid not in fittings]
    if missing:
        return 404, ErrorResponse(detail=f"Fitting not found: {missing[0]}")

    for row in payload.lines:
        if row.quantity < 1:
            return 400, ErrorResponse(detail="Quantity must be at least 1.")

    with transaction.atomic():
        order = FittingBuyOrder.objects.create(
            owner=request.user,
            notes=payload.notes,
            include_hull=payload.include_hull,
        )
        for index, row in enumerate(payload.lines):
            fitting = fittings[row.fitting_id]
            FittingBuyOrderLine.objects.update_or_create(
                order=order,
                fitting=fitting,
                defaults={
                    "quantity": row.quantity,
                    "sort_order": index,
                },
            )
        sync_order_items(order)
    ensure_jita_check(order, request.user, quiet=True)
    return 201, serialize_order_detail(order, request.user)
