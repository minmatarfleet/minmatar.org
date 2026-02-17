"""GET /{character_id}/tokens - get ESI tokens for character by ID."""

from typing import List

from app.errors import ErrorResponse
from authentication import AuthBearer
from esi.models import Token
from eveonline.endpoints.characters.schemas import CharacterTokenInfo
from eveonline.helpers.characters import character_desired_scopes
from eveonline.models import EveCharacter
from eveonline.scopes import scope_names, scope_group
from groups.helpers import PEOPLE_TEAM, TECH_TEAM, user_in_team

PATH = "{int:character_id}/tokens"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Get ESI tokens for character by ID",
    "auth": AuthBearer(),
    "response": {
        200: List[CharacterTokenInfo],
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def get_character_tokens(request, character_id: int):
    character = EveCharacter.objects.filter(character_id=character_id).first()
    if not character:
        return 404, ErrorResponse(detail="Character not found")
    is_admin = (
        request.user.is_superuser
        or user_in_team(request.user, PEOPLE_TEAM)
        or user_in_team(request.user, TECH_TEAM)
    )
    response = []
    for token in Token.objects.filter(character_id=character.character_id):
        if is_admin or token.user == request.user:
            scopes = scope_names(token)
            response.append(
                CharacterTokenInfo(
                    id=str(token.pk),
                    created=token.created,
                    expires=token.expires,
                    can_refresh=token.can_refresh,
                    owner_hash=token.character_owner_hash,
                    scopes=scopes,
                    requested_level=character.esi_token_level or "",
                    requested_count=len(character_desired_scopes(character)),
                    actual_level=scope_group(token) or "",
                    actual_count=len(scopes),
                    token_state=(
                        "SUSPENDED" if character.esi_suspended else "ACTIVE"
                    ),
                )
            )
    return response
