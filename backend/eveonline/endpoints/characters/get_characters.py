"""GET "" - get characters for current user or by primary_character_id."""

from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.characters.schemas import BasicCharacterResponse
from eveonline.helpers.characters import user_characters
from eveonline.models import EveCharacter

PATH = ""
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Get characters",
    "auth": AuthBearer(),
    "response": {200: List[BasicCharacterResponse], 404: ErrorResponse},
}


def get_characters(request, primary_character_id: int = None):
    if primary_character_id:
        if not EveCharacter.objects.filter(
            character_id=primary_character_id
        ).exists():
            return 404, ErrorResponse(detail="Primary character not found")
        character = EveCharacter.objects.get(character_id=primary_character_id)
        characters = user_characters(character.token.user)
    else:
        characters = user_characters(request.user)
    return [
        {"character_id": c.character_id, "character_name": c.character_name}
        for c in characters
    ]
