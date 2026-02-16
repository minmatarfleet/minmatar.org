"""GET /current - get current Eve player. One file, one endpoint."""

from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.characters.players.schemas import EvePlayerResponse
from eveonline.helpers.characters import user_player

router = Router(tags=["Players"])

ROUTE_SPEC = {
    "summary": "Get details of current Eve player",
    "auth": AuthBearer(),
    "response": {
        200: EvePlayerResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
}


@router.get("", **ROUTE_SPEC)
def get_current_player(request):
    player = user_player(request.user)
    if not player:
        return 404, ErrorResponse(detail="No player found for current user")
    return EvePlayerResponse(
        id=player.id,
        nickname=player.nickname,
        user_id=player.user_id,
        primary_character_id=player.primary_character_id,
        prime_time=player.prime_time,
    )
