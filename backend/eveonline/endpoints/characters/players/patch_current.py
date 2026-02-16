"""PATCH /current - update current Eve player. One file, one endpoint."""

from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.characters.players.schemas import (
    UpdateEvePlayerRequest,
)
from eveonline.helpers.characters import user_player

router = Router(tags=["Players"])

ROUTE_SPEC = {
    "summary": "Update details of current Eve player",
    "auth": AuthBearer(),
    "response": {200: None, 403: ErrorResponse, 404: ErrorResponse},
}


@router.patch("", **ROUTE_SPEC)
def patch_current_player(request, data: UpdateEvePlayerRequest):
    player = user_player(request.user)
    if not player:
        return 404, ErrorResponse(detail="No player found for current user")
    if data.prime_time:
        player.prime_time = data.prime_time
    if data.nickname:
        player.nickname = data.nickname
    player.save()
    return 200, None
