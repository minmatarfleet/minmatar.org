"""post_from_doctrine"""

from app.errors import ErrorResponse
from audit.helpers import record_change
from authentication import AuthBearer
from django.db import transaction
from eveonline.models import EveLocation
from fittings.models import EveDoctrine, EveDoctrineFitting
from market.models import (
    EveMarketContractExpectation,
)
from market.endpoints.hubs.common import (
    allowed,
    forbidden,
)
from market.endpoints.hubs.schemas import (
    FromDoctrineRequest,
    FromDoctrineResponse,
)

PATH = "/hubs/{location_id}/expectations/from-doctrine"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Track contracts for every fitting of a doctrine at a hub",
    "auth": AuthBearer(),
    "response": {
        200: FromDoctrineResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_from_doctrine(
    request, location_id: int, payload: FromDoctrineRequest
):
    if not allowed(request):
        return forbidden()
    location = EveLocation.objects.filter(location_id=location_id).first()
    doctrine = EveDoctrine.objects.filter(pk=payload.doctrine_id).first()
    if location is None or doctrine is None:
        return 404, ErrorResponse.new("Hub or doctrine not found")
    created = 0
    existing = 0
    with transaction.atomic():
        for fitting_id in EveDoctrineFitting.objects.filter(
            doctrine=doctrine
        ).values_list("fitting_id", flat=True):
            _, was_created = (
                EveMarketContractExpectation.objects.get_or_create(
                    location=location,
                    fitting_id=fitting_id,
                    defaults={"quantity": 1},
                )
            )
            if was_created:
                created += 1
            else:
                existing += 1
    record_change(
        request.user,
        f"Expectations set from doctrine {doctrine.name} at "
        f"{location.location_name}: {created} added",
    )
    return 200, FromDoctrineResponse(created=created, already_tracked=existing)
