"""GET /primary - get primary character. One file, one endpoint."""

from authentication import AuthBearer
from eveonline.endpoints.characters.schemas import BasicCharacterResponse
from eveonline.helpers.characters import user_primary_character

PATH = "primary"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Get primary character",
    "auth": AuthBearer(),
    "response": {200: BasicCharacterResponse, 404: dict},
}


def get_primary_character(request):
    char = user_primary_character(request.user)
    if char is None:
        return 404, {"detail": "Primary character not found."}
    return {
        "character_id": char.character_id,
        "character_name": char.character_name,
    }
