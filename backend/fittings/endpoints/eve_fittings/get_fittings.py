"""GET \"\" - list all ship fittings with refits."""

from typing import List

from fittings.endpoints.eve_fittings.schemas import FittingResponse
from fittings.endpoints.eve_fittings.serialization import make_fitting_response
from fittings.models import EveFitting

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "response": {200: List[FittingResponse]},
}


def get_fittings(request):
    fittings = EveFitting.objects.prefetch_related("refits")
    response = []
    for fitting in fittings:
        fitting_response = make_fitting_response(fitting)
        response.append(fitting_response)
    return response
