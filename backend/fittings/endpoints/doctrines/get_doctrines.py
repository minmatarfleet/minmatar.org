"""GET \"\" - list all doctrines with fittings by role."""

from typing import List

from fittings.endpoints.doctrines.schemas import DoctrineResponse
from fittings.endpoints.eve_fittings.serialization import make_fitting_response
from fittings.models import EveDoctrine

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "response": {200: List[DoctrineResponse]},
}


def get_doctrines(request):
    doctrines = EveDoctrine.objects.prefetch_related(
        "evedoctrinefitting_set__fitting__refits",
    )
    response = []
    for doctrine in doctrines:
        primary_fittings = []
        secondary_fittings = []
        support_fittings = []
        for doctrine_fitting in doctrine.evedoctrinefitting_set.all():
            fitting = doctrine_fitting.fitting
            fitting_response = make_fitting_response(fitting)
            if doctrine_fitting.role == "primary":
                primary_fittings.append(fitting_response)
            elif doctrine_fitting.role == "secondary":
                secondary_fittings.append(fitting_response)
            elif doctrine_fitting.role == "support":
                support_fittings.append(fitting_response)
        doctrine_response = DoctrineResponse(
            id=doctrine.id,
            name=doctrine.name,
            type=doctrine.type,
            created_at=doctrine.created_at,
            updated_at=doctrine.updated_at,
            description=doctrine.description,
            primary_fittings=primary_fittings,
            secondary_fittings=secondary_fittings,
            support_fittings=support_fittings,
            sig_ids=[],
            location_ids=[
                location.location_id for location in doctrine.locations.all()
            ],
        )
        response.append(doctrine_response)
    return response
