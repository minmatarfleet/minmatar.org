"""GET /systems/{system_id} - system industry view with optional freeport profile."""

from app.errors import ErrorResponse
from industry.endpoints.planner.schemas import SystemIndustrySchema
from industry.helpers.facility_api import system_industry

PATH = "systems/{int:system_id}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": (
        "System industry details: matching freeport profile (if configured) "
        "and live ESI manufacturing/reaction cost indices"
    ),
    "response": {
        200: SystemIndustrySchema,
        502: ErrorResponse,
    },
}


def get_system_industry(request, system_id: int):
    try:
        return system_industry(system_id)
    except ValueError as exc:
        return 502, ErrorResponse(detail=str(exc))
