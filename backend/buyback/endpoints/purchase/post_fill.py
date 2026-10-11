"""POST /stock/fill – preview a purchase against remaining buyback stock."""

from app.errors import ErrorResponse
from authentication import AuthOptional
from buyback.endpoints.purchase.serialization import fill_response
from buyback.endpoints.schemas import (
    BuybackPurchaseFillRequest,
    BuybackPurchaseFillResponse,
)
from buyback.helpers.auth import character_for_refine
from buyback.helpers.purchase_fill import fill_purchase

PATH = "/fill"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Match a need list to remaining buyback stock",
    "auth": AuthOptional(),
    "response": {
        200: BuybackPurchaseFillResponse,
        400: ErrorResponse,
        401: ErrorResponse,
        403: ErrorResponse,
    },
}


def post_fill(request, payload: BuybackPurchaseFillRequest):
    paste = (payload.paste or "").strip()
    if not paste:
        return 400, ErrorResponse(detail="Paste at least one item line.")
    character, auth_error = character_for_refine(request, payload.character_id)
    if auth_error is not None:
        return auth_error
    try:
        fill = fill_purchase(
            paste,
            character=character,
            facility_key=payload.facility_key,
            use_reprocessing_implants=payload.use_reprocessing_implants,
        )
    except ValueError as exc:
        return 400, ErrorResponse(detail=str(exc))
    return fill_response(fill)
