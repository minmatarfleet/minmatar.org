"""GET /invention/{type_id}/quote - the cheapest way to invent copies for a lot."""

from typing import Optional

from app.errors import ErrorResponse
from industry.endpoints.planner.schemas import PlanInventionSchema
from industry.helpers.facility_profiles import FACILITY_PROFILES
from industry.helpers.invention import InventionSkills
from industry.helpers.invention_planner import (
    InventionRequest,
    invention_to_dict,
    is_invented_product,
    quote_invention,
)

PATH = "invention/{int:type_id}/quote"
METHOD = "get"
ROUTE_SPEC = {
    "summary": (
        "Quote invention for a T2/T3 product at a freeport: chance, copies, "
        "expected and buy-list attempts, cost per unit, and the alternatives"
    ),
    "response": {
        200: PlanInventionSchema,
        400: ErrorResponse,
        404: ErrorResponse,
        502: ErrorResponse,
    },
}


def get_invention_quote(
    request,
    type_id: int,
    quantity: int = 1,
    facility_key: str = "amamake",
    decryptor: str = "auto",
    source_type_id: Optional[int] = None,
    science_1: int = 5,
    science_2: int = 5,
    encryption: int = 4,
):
    if not is_invented_product(type_id):
        return 404, ErrorResponse(detail=f"Type {type_id} is not invented")
    key = facility_key.lower().strip()
    if key not in FACILITY_PROFILES:
        return 400, ErrorResponse(detail=f"Unknown facility {facility_key!r}")
    if quantity < 1:
        return 400, ErrorResponse(detail="quantity must be >= 1")
    if any(
        level < 0 or level > 5 for level in (science_1, science_2, encryption)
    ):
        return 400, ErrorResponse(detail="invention skill levels must be 0-5")
    invention_request = InventionRequest(
        decryptor=(decryptor or "auto").strip().lower(),
        source_type_id=source_type_id,
        skills=InventionSkills(
            science_1=science_1, science_2=science_2, encryption=encryption
        ),
    )
    try:
        choice = quote_invention(type_id, quantity, key, invention_request)
    except ValueError as exc:
        msg = str(exc)
        if "cost index" in msg.lower() or "esi" in msg.lower():
            return 502, ErrorResponse(detail=msg)
        return 400, ErrorResponse(detail=msg)
    return 200, invention_to_dict(choice)
