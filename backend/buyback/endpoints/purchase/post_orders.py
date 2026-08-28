"""POST /stock/orders – place a pending buyback purchase."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from buyback.endpoints.purchase.serialization import order_response
from buyback.endpoints.schemas import (
    BuybackPurchaseFillRequest,
    BuybackPurchaseOrderResponse,
)
from buyback.helpers.auth import character_for_refine
from buyback.helpers.purchase_orders import (
    PurchaseOrderError,
    create_purchase_order,
)
from buyback.models import BuybackPurchaseOrder

PATH = "/orders"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Place a pending buyback purchase order",
    "auth": AuthBearer(),
    "response": {
        201: BuybackPurchaseOrderResponse,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
        409: ErrorResponse,
    },
}


def post_orders(request, payload: BuybackPurchaseFillRequest):
    paste = (payload.paste or "").strip()
    if not paste:
        return 400, ErrorResponse(detail="Paste at least one item line.")
    character, auth_error = character_for_refine(request, payload.character_id)
    if auth_error is not None:
        return auth_error
    try:
        order = create_purchase_order(
            user=request.user,
            paste=paste,
            source=payload.source or BuybackPurchaseOrder.Source.STOCKPILE,
            character=character,
            facility_key=payload.facility_key,
            use_reprocessing_implants=payload.use_reprocessing_implants,
        )
    except ValueError as exc:
        return 400, ErrorResponse(detail=str(exc))
    except PurchaseOrderError as exc:
        detail = str(exc)
        status = 409 if "no longer available" in detail.lower() else 400
        return status, ErrorResponse(detail=detail)
    order = (
        BuybackPurchaseOrder.objects.prefetch_related("lines")
        .select_related("created_by")
        .get(pk=order.pk)
    )
    return 201, order_response(order)
