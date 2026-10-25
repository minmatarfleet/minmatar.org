"""GET /training/characters/{character_id}/ships - doctrine fits a character can train for, those in the most doctrines first."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from capabilities import training
from capabilities.endpoints.schemas import ShipOptionResponse

PATH = "/characters/{character_id}/ships"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Doctrine fits a character can train for, those in the most doctrines first",
    "auth": AuthBearer(),
    "response": {200: list[ShipOptionResponse], 404: ErrorResponse},
}


def get_ships(request, character_id: int):
    try:
        return 200, training.ship_options(request.user, character_id)
    except training.TrainingError as exc:
        return 404, ErrorResponse(detail=str(exc))
