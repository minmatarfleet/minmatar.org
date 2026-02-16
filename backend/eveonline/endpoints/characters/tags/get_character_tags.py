"""GET /{character_id}/tags - get tags for a character. One file, one endpoint."""

from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.characters._helpers import can_manage_tags
from eveonline.endpoints.characters.schemas import CharacterTagResponse
from eveonline.models import EveCharacter, EveCharacterTag

PATH = "{int:character_id}/tags"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Get tags for a character",
    "auth": AuthBearer(),
    "response": {
        200: List[CharacterTagResponse],
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def get_character_tags(request, character_id: int):
    character = EveCharacter.objects.filter(character_id=character_id).first()
    if not character:
        return 403, ErrorResponse(detail="Character not found")
    if not can_manage_tags(request.user, character):
        return 403, ErrorResponse(
            detail="Cannot manage tags for this character"
        )
    tags = EveCharacterTag.objects.filter(character=character)
    return [
        CharacterTagResponse(
            id=tag.tag_id,
            title=tag.tag.title,
            description=tag.tag.description,
            image_name=tag.tag.image_name,
        )
        for tag in tags
    ]
