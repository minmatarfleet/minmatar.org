"""GET /{character_id}/skillsets - get skillsets for character by ID."""

import json
from typing import List

from authentication import AuthBearer
from eveonline.endpoints.characters.schemas import CharacterSkillsetResponse
from eveonline.models import EveCharacter, EveCharacterSkillset

PATH = "{int:character_id}/skillsets"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Get skillsets for character by ID",
    "auth": AuthBearer(),
    "response": {200: List[CharacterSkillsetResponse], 403: dict, 404: dict},
}


def get_skillsets_for_character_by_id(request, character_id: int):
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
    skillsets = EveCharacterSkillset.objects.filter(character=character)
    return [
        {
            "name": s.eve_skillset.name,
            "progress": s.progress,
            "missing_skills": json.loads(s.missing_skills),
        }
        for s in skillsets
    ]
