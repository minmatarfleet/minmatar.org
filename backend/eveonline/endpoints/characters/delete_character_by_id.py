"""DELETE /{character_id} - delete character by ID."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from audit.models import AuditEntry
from esi.models import Token
from eveonline.helpers.characters import (
    set_primary_character,
    user_primary_character,
)
from eveonline.models import EveCharacter

PATH = "{int:character_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "summary": "Delete character by ID",
    "auth": AuthBearer(),
    "response": {
        200: None,
        403: ErrorResponse,
        404: ErrorResponse,
        500: ErrorResponse,
    },
}


def delete_character_by_id(request, character_id: int):
    if not EveCharacter.objects.filter(character_id=character_id).exists():
        return 404, {"detail": "Character not found."}
    if not (
        request.user.has_perm("eveonline.delete_evecharacter")
        or Token.objects.filter(
            user=request.user, character_id=character_id
        ).exists()
    ):
        return 403, {
            "detail": "You do not have permission to delete this character."
        }
    primary_character = user_primary_character(request.user)
    if primary_character and primary_character.character_id == character_id:
        characters = EveCharacter.objects.filter(user=request.user).exclude(
            character_id=character_id
        )
        if characters.exists():
            set_primary_character(request.user, characters.first())
    try:
        AuditEntry.objects.create(
            user=request.user,
            category="character_deleted",
            summary=f"User {request.user.username} deleted character {character_id}",
        )
        EveCharacter.objects.filter(character_id=character_id).delete()
        Token.objects.filter(character_id=character_id).delete()
    except Exception as e:
        return 500, ErrorResponse.new(
            f"Error deleting character {character_id}", str(e)
        )
    return 200, None
