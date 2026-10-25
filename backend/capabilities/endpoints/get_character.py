"""GET /training/characters/{character_id} - one of your characters: its ships, the ones close, ready ships per role."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from capabilities import training
from capabilities.endpoints.schemas import TrainingCharacterResponse

PATH = "/characters/{character_id}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "One of your characters: its ships, the ones close, ready ships per role",
    "auth": AuthBearer(),
    "response": {200: TrainingCharacterResponse, 404: ErrorResponse},
}


def get_character(request, character_id: int):
    try:
        return 200, training.character_view(request.user, character_id)
    except training.TrainingError as exc:
        return 404, ErrorResponse(detail=str(exc))
