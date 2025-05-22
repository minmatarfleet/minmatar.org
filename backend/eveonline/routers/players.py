import logging
from typing import Optional

from ninja import Router
from pydantic import BaseModel

from authentication import AuthBearer

from eveonline.helpers.characters import user_player

logger = logging.getLogger(__name__)

router = Router(tags=["Players"])


class ErrorResponse(BaseModel):
    detail: str


class EvePlayerResponse(BaseModel):
    id: int
    nickname: Optional[str]
    user_id: int
    primary_character_id: Optional[int]
    prime_time: Optional[str]


class UpdateEvePlayerRequest(BaseModel):
    nickname: Optional[str]
    prime_time: Optional[str]


@router.get(
    "/current",
    summary="Get details of current Eve player",
    auth=AuthBearer(),
    response={200: EvePlayerResponse, 403: ErrorResponse, 404: ErrorResponse},
)
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


@router.patch(
    "/current",
    summary="Update details of current Eve player",
    auth=AuthBearer(),
    response={200: None, 403: ErrorResponse, 404: ErrorResponse},
)
def update_current_player(request, data: UpdateEvePlayerRequest):

    player = user_player(request.user)

    if not player:
        return 404, ErrorResponse(detail="No player found for current user")

    if data.prime_time:
        player.prime_time = data.prime_time

    if data.nickname:
        player.nickname = data.nickname

    player.save()

    return 200, None
