"""DELETE /{character_id}/tags/{tag_id} - remove a tag from a character."""

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.characters._helpers import can_manage_tags
from eveonline.models import EveCharacter, EveCharacterTag

PATH = "{int:character_id}/tags/{int:tag_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "summary": "Remove a tag from a character",
    "auth": AuthBearer(),
    "response": {200: None, 403: ErrorResponse, 404: ErrorResponse},
}


def delete_character_tag(request, character_id: int, tag_id: int):
    character = EveCharacter.objects.get(character_id=character_id)
    if not can_manage_tags(request.user, character):
        return 403, ErrorResponse(detail="Cannot manage tags for this user")
    EveCharacterTag.objects.filter(character=character, id=tag_id).delete()
    return 200
