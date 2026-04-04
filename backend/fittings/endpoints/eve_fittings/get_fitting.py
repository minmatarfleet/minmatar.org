"""GET /{fitting_id} - fetch one fitting with refits."""

from app.errors import ErrorResponse

from fittings.endpoints.eve_fittings.schemas import FittingResponse
from fittings.endpoints.eve_fittings.serialization import make_fitting_response
from fittings.models import EveFitting

PATH = "{int:fitting_id}"
METHOD = "get"
ROUTE_SPEC = {
    "response": {200: FittingResponse, 404: ErrorResponse},
}


def get_fitting(request, fitting_id: int):
    if not EveFitting.objects.filter(id=fitting_id).exists():
        return 404, ErrorResponse(
            detail=f"Fitting not found: {fitting_id}",
        )
    fitting = EveFitting.objects.prefetch_related("refits").get(id=fitting_id)
    fitting_response = make_fitting_response(fitting)
    return fitting_response
