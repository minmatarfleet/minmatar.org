"""GET /fitting-buy-orders/{order_id}/check-jita/{check_id} — poll progress."""

from ninja import Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from market.endpoints.fitting_buy_orders.common import get_order_or_404
from market.helpers.fitting_buy_serialize import (
    FittingBuyJitaCheckSchema,
    FittingBuyOrderDetailSchema,
    serialize_jita_check,
    serialize_order_detail,
)
from market.models.fitting_buy_order import (
    FittingBuyJitaCheck,
    FittingBuyJitaCheckStatus,
)

PATH = "/fitting-buy-orders/{order_id}/check-jita/{check_id}"
METHOD = "get"


class JitaCheckPollResponse(Schema):
    check: FittingBuyJitaCheckSchema
    order: FittingBuyOrderDetailSchema | None = None


ROUTE_SPEC = {
    "response": {
        200: JitaCheckPollResponse,
        404: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Poll a fitting buy Jita check",
}


def get_fitting_buy_check_jita(request, order_id: int, check_id: int):
    order, err = get_order_or_404(order_id)
    if err:
        return err
    check = FittingBuyJitaCheck.objects.filter(
        order=order, pk=check_id
    ).first()
    if check is None:
        return 404, ErrorResponse(detail="Jita check not found.")

    order_payload = None
    if check.status in (
        FittingBuyJitaCheckStatus.COMPLETE,
        FittingBuyJitaCheckStatus.FAILED,
    ):
        order_payload = serialize_order_detail(order, request.user)
    return {
        "check": serialize_jita_check(check),
        "order": order_payload,
    }
