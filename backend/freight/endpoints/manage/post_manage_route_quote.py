"""POST /manage/routes/quote - price the editor's unsaved values."""

from authentication import AuthBearer
from app.errors import ErrorResponse
from freight.endpoints.manage.common import (
    RouteQuote,
    RouteQuoteRequest,
    can_manage,
    forbidden,
    quote_schema,
)
from freight.models import EveFreightRoute

PATH = "/manage/routes/quote"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Sample quote and warnings for unsaved route pricing",
    "auth": AuthBearer(),
    "response": {
        200: RouteQuote,
        400: ErrorResponse,
        403: ErrorResponse,
    },
}


def post_manage_route_quote(request, payload: RouteQuoteRequest):
    if not can_manage(request.user):
        return forbidden()
    if payload.route_type not in EveFreightRoute.RouteType.values:
        return 400, ErrorResponse.new("Unknown route type")
    # Never saved: only priced.
    route = EveFreightRoute(**payload.model_dump())
    return 200, quote_schema(route)
