"""GET /{order_id}/claim-characters - the user's characters that can claim."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.helpers.characters import (
    user_characters,
    user_primary_character,
)
from industry.endpoints.orders.schemas import (
    OrderClaimCharacterResponse,
    OrderClaimCharactersResponse,
)
from industry.models import IndustryOrder
from structures import dock_access

PATH = "{int:order_id}/claim-characters"
METHOD = "get"
ROUTE_SPEC = {
    "summary": (
        "Your characters that can dock at the order's delivery location"
    ),
    "auth": AuthBearer(),
    "response": {200: OrderClaimCharactersResponse, 404: ErrorResponse},
}


def get_order_claim_characters(request, order_id: int):
    order = (
        IndustryOrder.objects.filter(pk=order_id)
        .select_related("location")
        .first()
    )
    if order is None:
        return 404, ErrorResponse(detail=f"Order {order_id} not found.")
    location = order.location
    primary = user_primary_character(request.user)
    primary_id = primary.character_id if primary else None
    characters = sorted(
        (
            character
            for character in user_characters(request.user)
            if location is None
            or dock_access.character_can_dock(location, character)
        ),
        key=lambda c: (
            c.character_id != primary_id,
            (c.character_name or "").lower(),
        ),
    )
    return 200, OrderClaimCharactersResponse(
        restricted=bool(location and dock_access.is_restricted(location)),
        location_name=(
            (location.short_name or location.location_name) if location else ""
        ),
        dock_tickers=dock_access.dock_tickers(location) if location else [],
        characters=[
            OrderClaimCharacterResponse(
                character_id=character.character_id,
                character_name=character.character_name or "",
                is_primary=character.character_id == primary_id,
            )
            for character in characters
        ],
    )
