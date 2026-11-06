"""get_hub_expectations"""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.models import EveLocation
from fittings.models import EveDoctrine
from market.helpers.expectations_admin import (
    build_contract_expectation_rows,
    build_fitting_expectation_rows,
)
from market.models import (
    EveMarketItemExpectation,
)
from market.endpoints.hubs.common import (
    allowed,
    forbidden,
)
from market.endpoints.hubs.schemas import (
    FittingExpectationRow,
    ItemExpectationRow,
    DoctrineOption,
    HubExpectationsResponse,
)

PATH = "/hubs/{location_id}/expectations"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Stocking expectations at a hub",
    "auth": AuthBearer(),
    "response": {
        200: HubExpectationsResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def get_hub_expectations(request, location_id: int):
    if not allowed(request):
        return forbidden()
    location = EveLocation.objects.filter(location_id=location_id).first()
    if location is None:
        return 404, ErrorResponse.new("Hub not found")
    fittings = [
        FittingExpectationRow(
            fitting_id=row["fitting_id"],
            fitting_name=row["fitting_name"],
            tracked=row["quantity"] is not None,
        )
        for row in build_fitting_expectation_rows(location)
    ]
    contracts = [
        FittingExpectationRow(
            fitting_id=row["fitting_id"],
            fitting_name=row["fitting_name"],
            tracked=row["quantity"] is not None,
            current=row["current"],
        )
        for row in build_contract_expectation_rows(location)
    ]
    items = [
        ItemExpectationRow(type_id=e.item_id, name=e.item.name)
        for e in EveMarketItemExpectation.objects.filter(location=location)
        .select_related("item")
        .order_by("item__name")
    ]
    doctrines = [
        DoctrineOption(id=d.id, name=d.name)
        for d in EveDoctrine.objects.order_by("name")
    ]
    return 200, HubExpectationsResponse(
        location_id=location.location_id,
        fittings=fittings,
        contracts=contracts,
        items=items,
        doctrines=doctrines,
    )
