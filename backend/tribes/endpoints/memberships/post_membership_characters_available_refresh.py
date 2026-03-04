"""POST "/{tribe_id}/groups/{group_id}/memberships/characters-available/refresh" - refresh skills and assets for one character (sync, no queue)."""

from django.core.cache import cache

from authentication import AuthBearer
from esi.models import Token
from eveonline.helpers.characters.update import (
    update_character_assets,
    update_character_skills,
)
from eveonline.models import EveCharacter
from tribes.endpoints.memberships.get_membership_characters_available import (
    _build_available_character_schema,
)
from tribes.endpoints.memberships.schemas import (
    AvailableCharacterSchema,
    RefreshAvailableCharacterRequest,
)
from tribes.models import TribeGroup

REFRESH_COOLDOWN_SECONDS = 3600  # 1 hour per character
CACHE_KEY_PREFIX = "tribe_available_refresh"

PATH = "/{tribe_id}/groups/{group_id}/memberships/characters-available/refresh"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Refresh skills and assets for one of your characters (manual, no queue). Once per character per hour.",
    "response": {
        200: AvailableCharacterSchema,
        400: dict,
        404: dict,
        429: dict,
    },
    "auth": AuthBearer(),
}

SCOPE_ASSETS = ["esi-assets.read_assets.v1"]
SCOPE_SKILLS = ["esi-skills.read_skills.v1"]


def post_membership_characters_available_refresh(
    request,
    tribe_id: int,
    group_id: int,
    payload: RefreshAvailableCharacterRequest,
):
    tg = (
        TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id)
        .prefetch_related(
            "requirements__asset_types__eve_type",
            "requirements__qualifying_skills__eve_type",
        )
        .first()
    )
    if not tg:
        return 404, {"detail": "TribeGroup not found."}

    character = EveCharacter.objects.filter(
        character_id=payload.character_id, user=request.user
    ).first()
    if not character:
        return 404, {"detail": "Character not found or not yours."}

    cache_key = f"{CACHE_KEY_PREFIX}:{request.user.pk}:{payload.character_id}"
    if cache.get(cache_key) is not None:
        return 429, {
            "detail": "Refresh allowed once per character per hour.",
            "retry_after_seconds": REFRESH_COOLDOWN_SECONDS,
        }

    has_assets = Token.get_token(payload.character_id, SCOPE_ASSETS)
    has_skills = Token.get_token(payload.character_id, SCOPE_SKILLS)
    if not has_assets and not has_skills:
        return 400, {
            "detail": "Character has no token with assets or skills scope. Re-add the character with the correct scopes."
        }

    if has_assets:
        update_character_assets(payload.character_id)
    if has_skills:
        update_character_skills(payload.character_id)

    cache.set(cache_key, 1, timeout=REFRESH_COOLDOWN_SECONDS)

    character.refresh_from_db()
    schema = _build_available_character_schema(character, tg)
    return 200, schema
