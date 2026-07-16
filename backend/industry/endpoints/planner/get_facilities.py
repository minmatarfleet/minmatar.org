"""GET /facilities - list alliance freeport facility profiles."""

from typing import List

from industry.endpoints.planner.schemas import FacilitySummarySchema
from industry.helpers.facility_api import list_facility_summaries

PATH = "facilities"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List alliance freeport facility profiles (Amamake, Basgerin)",
    "response": {
        200: List[FacilitySummarySchema],
    },
}


def get_facilities(request):
    return list_facility_summaries()
