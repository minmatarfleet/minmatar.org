"""PUT /primary - set primary character. One file, one endpoint."""

from authentication import AuthBearer
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter

PATH = "primary"
METHOD = "put"
ROUTE_SPEC = {
    "summary": "Set primary character",
    "auth": AuthBearer(),
    "response": {200: None, 403: dict, 404: dict},
}


def put_primary_character(request, character_id: int):
    character = EveCharacter.objects.filter(character_id=character_id).first()
    if not character:
        return 404, {"detail": f"Character {character_id} not found."}
    if character.user != request.user:
        return 403, {
            "detail": "You do not have permission to set this character as primary."
        }
    set_primary_character(request.user, character)
    return 200, None
