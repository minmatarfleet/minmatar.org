"""POST /fitting-buy-orders/{order_id}/lines/{line_id}/swaps."""

from ninja import Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveuniverse.models import EveType
from market.endpoints.fitting_buy_orders.common import (
    get_order_or_404,
    require_owner,
)
from market.helpers.fitting_buy_check import ensure_jita_check
from market.helpers.fitting_buy_plan import sync_order_items
from market.helpers.fitting_buy_serialize import (
    FittingBuyOrderDetailSchema,
    serialize_order_detail,
)
from market.helpers.fitting_buy_swap import apply_swap_on_line
from market.models.fitting_buy_order import FittingBuyOrderLine

PATH = "/fitting-buy-orders/{order_id}/lines/{line_id}/swaps"
METHOD = "post"
ROUTE_SPEC = {
    "response": {
        200: FittingBuyOrderDetailSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Apply a module swap on a fitting buy line",
}


class ApplySwapRequest(Schema):
    preferred_type_id: int
    substitute_type_id: int
    notes: str = ""


def post_fitting_buy_swap(
    request, order_id: int, line_id: int, payload: ApplySwapRequest
):
    order, err = get_order_or_404(order_id)
    if err:
        return err
    denied = require_owner(request, order)
    if denied:
        return denied

    line = FittingBuyOrderLine.objects.filter(order=order, pk=line_id).first()
    if line is None:
        return 404, ErrorResponse(detail="Line not found.")

    if payload.preferred_type_id == payload.substitute_type_id:
        return 400, ErrorResponse(
            detail="Substitute must differ from preferred."
        )

    types = {
        t.id: t
        for t in EveType.objects.filter(
            id__in=[payload.preferred_type_id, payload.substitute_type_id]
        )
    }
    if payload.preferred_type_id not in types:
        return 404, ErrorResponse(detail="Preferred module type not found.")
    if payload.substitute_type_id not in types:
        return 404, ErrorResponse(detail="Substitute module type not found.")

    apply_swap_on_line(
        line,
        preferred_type_id=payload.preferred_type_id,
        substitute_type_id=payload.substitute_type_id,
        notes=payload.notes or "",
    )
    sync_order_items(order)
    ensure_jita_check(order, request.user, quiet=True)
    return serialize_order_detail(order, request.user)
