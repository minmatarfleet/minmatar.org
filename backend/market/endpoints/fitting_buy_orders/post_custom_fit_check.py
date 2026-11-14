"""POST /fitting-buy-orders/custom-fit-check — check a pasted EFT fit."""

from ninja import Schema

from app.errors import ErrorResponse
from authentication import AuthBearer
from fittings.eft import item_quantities
from market.helpers.fitting_buy_custom import resolve_custom_fit


class CustomFitCheckRequest(Schema):
    eft: str


class CustomFitCheckResponse(Schema):
    ok: bool
    error: str = ""
    ship_id: int | None = None
    ship_name: str = ""
    fit_name: str = ""
    item_count: int = 0
    unknown_names: list[str] = []


PATH = "/fitting-buy-orders/custom-fit-check"
METHOD = "post"
ROUTE_SPEC = {
    "response": {
        200: CustomFitCheckResponse,
        401: ErrorResponse,
    },
    "auth": AuthBearer(),
    "summary": "Check a pasted EFT fit before adding it to a buy order",
}


def post_fitting_buy_custom_fit_check(request, payload: CustomFitCheckRequest):
    fit = resolve_custom_fit(payload.eft)
    # Everything below the header: modules, charges, drones and cargo.
    item_count = 0
    if fit.ship_name:
        item_count = max(0, sum(item_quantities(fit.eft).values()) - 1)
    return CustomFitCheckResponse(
        ok=fit.ok,
        error=fit.error,
        ship_id=fit.ship_id,
        ship_name=fit.ship_name,
        fit_name=fit.fit_name,
        item_count=item_count,
        unknown_names=fit.unknown_names,
    )
