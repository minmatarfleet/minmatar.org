"""DELETE /{character_id} - remove character from the user's account."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers.feature_access import can_use_feature
from audit.models import AuditEntry
from esi.models import Token
from eveonline.helpers.characters import (
    orphan_character,
    set_primary_character,
    user_player,
    user_primary_character,
)
from eveonline.models import EveCharacter

PATH = "{int:character_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "summary": "Remove character from account",
    "auth": AuthBearer(),
    "response": {
        200: None,
        403: ErrorResponse,
        404: ErrorResponse,
        500: ErrorResponse,
    },
}


def delete_character_by_id(request, character_id: int):
    character = EveCharacter.objects.filter(character_id=character_id).first()
    if not character:
        return 404, {"detail": "Character not found."}
    if not (
        can_use_feature(request.user, "characters.delete_staff")
        or Token.objects.filter(
            user=request.user, character_id=character_id
        ).exists()
    ):
        return 403, {
            "detail": "You do not have permission to delete this character."
        }
    primary_character = user_primary_character(request.user)
    if primary_character and primary_character.character_id == character_id:
        other_character = (
            EveCharacter.objects.filter(user=request.user)
            .exclude(character_id=character_id)
            .first()
        )
        if other_character:
            set_primary_character(request.user, other_character)
        else:
            player = user_player(request.user)
            if player:
                player.primary_character = None
                player.save(update_fields=["primary_character"])
    try:
        AuditEntry.objects.create(
            user=request.user,
            character=character,
            category="character_deleted",
            summary=(
                f"User {request.user.username} removed character "
                f"{character.character_name} ({character_id})"
            ),
        )
        orphan_character(character, acting_user=request.user)
    except Exception as e:
        return 500, ErrorResponse.new(
            f"Error removing character {character_id}", str(e)
        )
    return 200, None
