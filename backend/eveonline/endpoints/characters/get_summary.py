"""GET /summary - summary of character information for a user."""

from django.db.models import Count

from app.errors import ErrorResponse
from authentication import AuthBearer
from discord.models import DiscordUser
from eveonline.endpoints.characters._helpers import build_character_response
from eveonline.endpoints.characters.schemas import UserCharacterResponse
from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCharacter

PATH = "summary"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Returns a summary of character information for a user",
    "auth": AuthBearer(),
    "response": {
        200: UserCharacterResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


def get_summary(
    request, discord_id: int = None, character_name: str = None
) -> UserCharacterResponse:
    if discord_id or character_name:
        if not request.user.is_superuser:
            return 403, ErrorResponse(detail="Not authorised")
        if discord_id and character_name:
            return 400, ErrorResponse(
                detail="Only 1 query parameter supported"
            )
    if character_name:
        char = EveCharacter.objects.filter(
            character_name=character_name
        ).first()
        if not char:
            return 404, ErrorResponse(detail="No matching character found")
        if not char.user:
            return 400, ErrorResponse.log(
                "Character not linked to a user", char.id
            )
        char_user = char.user
        discord_user = DiscordUser.objects.filter(user=char_user).first()
    elif discord_id:
        discord_user = DiscordUser.objects.filter(id=discord_id).first()
        if not discord_user:
            return 404, ErrorResponse.log(
                "No matching discord user found", discord_id
            )
        char_user = discord_user.user
    else:
        char_user = request.user
        discord_user = DiscordUser.objects.filter(user=char_user).first()
        if not discord_user:
            return 404, ErrorResponse(detail="No matching discord user found")
    response = UserCharacterResponse(
        user_id=char_user.id,
        user_name=char_user.username,
        discord_id=str(discord_user.id),
        characters=[],
    )
    primary = user_primary_character(char_user)
    chars = EveCharacter.objects.filter(user=char_user).annotate(
        tag_count=Count("evecharactertag", distinct=True),
    )
    for char in chars:
        response.characters.append(build_character_response(char, primary))
    return response
