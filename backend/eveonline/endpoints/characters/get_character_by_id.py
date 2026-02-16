"""GET /{character_id} - get character by ID."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.characters.schemas import CharacterResponse
from eveonline.helpers.characters import character_primary
from eveonline.models import EveCharacter

PATH = "{int:character_id}"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Get character by ID",
    "auth": AuthBearer(),
    "response": {
        200: CharacterResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def get_character_by_id(request, character_id: int):
    if not EveCharacter.objects.filter(character_id=character_id).exists():
        return 404, ErrorResponse(detail="Character not found")
    character = EveCharacter.objects.get(character_id=character_id)
    payload = {
        "character_id": character.character_id,
        "character_name": character.character_name,
    }
    if character.token:
        primary_character = character_primary(character)
        if (
            primary_character
            and primary_character.character_id != character_id
        ):
            payload["primary_character_id"] = primary_character.character_id
            payload["primary_character_name"] = (
                primary_character.character_name
            )
    if (
        request.user.has_perm("eveonline.view_evecharacter")
        or request.user.is_superuser
        or (character.token and character.token.user == request.user)
    ):
        return payload
    return 403, {
        "detail": "You do not have permission to view this character."
    }
