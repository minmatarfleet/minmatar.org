"""GET /facilities/{facility_key} - facility detail with live ESI cost indices."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.endpoints.planner.schemas import FacilityDetailSchema
from industry.helpers.facility_api import facility_detail
from industry.helpers.facility_profiles import FACILITY_PROFILES

PATH = "facilities/{facility_key}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": (
        "Facility profile detail: structures, job-class bonuses, "
        "and live ESI cost indices for the facility system"
    ),
    "auth": AuthBearer(),
    "response": {
        200: FacilityDetailSchema,
        401: ErrorResponse,
        404: ErrorResponse,
        502: ErrorResponse,
    },
}


def get_facility(request, facility_key: str):
    key = facility_key.lower().strip()
    if key not in FACILITY_PROFILES:
        return 404, ErrorResponse(detail=f"Unknown facility {facility_key!r}")
    try:
        return facility_detail(key)
    except ValueError as exc:
        return 502, ErrorResponse(detail=str(exc))
