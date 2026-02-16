"""PUT /{character_id}/tags - replace a character's tags. One file, one endpoint."""

from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.characters._helpers import (
    add_tags_for_character,
    can_manage_tags,
)
from eveonline.models import EveCharacter, EveCharacterTag

PATH = "{int:character_id}/tags"
METHOD = "put"
ROUTE_SPEC = {
    "summary": "Replace a character's tags",
    "auth": AuthBearer(),
    "response": {200: None, 403: ErrorResponse, 404: ErrorResponse},
}


def put_character_tags(request, character_id: int, payload: List[int]):
    character = EveCharacter.objects.get(character_id=character_id)
    if not can_manage_tags(request.user, character):
        return 403, ErrorResponse(detail="Cannot manage tags for this user")
    EveCharacterTag.objects.filter(character=character).delete()
    add_tags_for_character(character, payload)
    return 200
