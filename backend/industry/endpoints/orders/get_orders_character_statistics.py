"""GET /character-statistics – delivered ISK estimate in last 30 days by primary character."""

from typing import List

from industry.endpoints.orders.schemas import (
    IndustryOrderCharacterStatResponse,
)
from industry.helpers.orders_character_statistics import (
    build_orders_character_statistics,
)

PATH = "character-statistics"
METHOD = "get"
ROUTE_SPEC = {
    "summary": (
        "Manufacturers with delivered industry-order ISK estimates in the "
        "past 30 days, keyed by primary character. Restricted to active "
        "members of manufacturing production tribe groups."
    ),
    "response": List[IndustryOrderCharacterStatResponse],
}


def get_orders_character_statistics(request):
    return [
        IndustryOrderCharacterStatResponse(**row)
        for row in build_orders_character_statistics()
    ]
