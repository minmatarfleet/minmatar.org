"""GET /{character_id}/assets - get assets for character by ID."""

from typing import List

from authentication import AuthBearer
from eveonline.endpoints.characters.schemas import CharacterAssetResponse
from eveonline.models import EveCharacter, EveCharacterAsset

PATH = "{int:character_id}/assets"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Get assets for character by ID",
    "auth": AuthBearer(),
    "response": {200: List[CharacterAssetResponse], 403: dict, 404: dict},
}


def get_assets_for_character_by_id(request, character_id: int):
    if not EveCharacter.objects.filter(character_id=character_id).exists():
        return 404, {"detail": "Character not found."}
    character = EveCharacter.objects.get(character_id=character_id)
    if not (
        request.user.has_perm("eveonline.view_evecharacter")
        or (character.token and character.token.user == request.user)
    ):
        return 403, {
            "detail": "You do not have permission to view this character."
        }
    assets = EveCharacterAsset.objects.filter(character=character)
    return [
        {
            "type_id": a.type_id,
            "type_name": a.type_name,
            "location_id": a.location_id,
            "location_name": a.location_name,
        }
        for a in assets
    ]
