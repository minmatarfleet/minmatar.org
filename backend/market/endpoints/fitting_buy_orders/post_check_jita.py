"""POST /fitting-buy-orders/{order_id}/check-jita — start progressive check."""

from ninja import Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from market.endpoints.fitting_buy_orders.common import (
    get_order_or_404,
    require_owner,
)
from market.helpers.fitting_buy_check import (
    JitaThrottleError,
    ensure_jita_check,
)
from market.helpers.fitting_buy_serialize import (
    FittingBuyJitaCheckSchema,
    serialize_jita_check,
)

PATH = "/fitting-buy-orders/{order_id}/check-jita"
METHOD = "post"
ROUTE_SPEC = {
    "response": {
        202: FittingBuyJitaCheckSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
        429: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Start a live Jita depth check for a buy order",
}


class StartJitaCheckRequest(Schema):
    force_refresh: bool = False
    type_ids: list[int] | None = None


def post_fitting_buy_check_jita(
    request, order_id: int, payload: StartJitaCheckRequest
):
    order, err = get_order_or_404(order_id)
    if err:
        return err
    denied = require_owner(request, order)
    if denied:
        return denied

    try:
        check = ensure_jita_check(
            order,
            request.user,
            force_refresh=payload.force_refresh,
            quiet=False,
            type_ids=payload.type_ids,
        )
    except JitaThrottleError as exc:
        return 429, ErrorResponse(detail=str(exc))
    except RuntimeError as exc:
        return 400, ErrorResponse(detail=str(exc))

    if check is None:
        return 400, ErrorResponse(
            detail="Nothing left to buy — no Jita check needed."
        )
    return 202, serialize_jita_check(check)
