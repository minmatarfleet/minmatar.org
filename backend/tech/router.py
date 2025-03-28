import logging

from ninja import Router
from typing import List, Optional

from django.conf import settings
from pydantic import BaseModel
from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers import TECH_TEAM, user_in_team
from eveonline.models import EveCharacter
from eveonline.client import EsiClient, EsiCorporation

router = Router(tags=["Tech"])
logger = logging.getLogger(__name__)


@router.get(
    "/ping",
    description="Check that the server is available. Always returns 'OK'.",
    response={200: str},
)
def ping(request):
    return "OK"


@router.get(
    "/auth_ping",
    description="Verify authentication.",
    auth=AuthBearer(),
    response={200: str, 403: ErrorResponse},
)
def auth_ping(request):
    return "Authorised"


@router.get(
    "/checkvar",
    description="Check that an env var has been set on the server.",
    auth=AuthBearer(),
    response={200: str, 403: ErrorResponse},
)
def check_var(request, var_name: str) -> str:
    if not user_in_team(request.user, TECH_TEAM):
        return 403, "Not authorised"
    if hasattr(settings, var_name):
        return "Set"
    else:
        return "Not set"


class TokenUserCharacterResponse(BaseModel):
    character_id: int
    character_name: str
    token_user_id: Optional[int] = None
    token_user_name: Optional[str] = None


@router.get(
    "/no_user_char",
    description="Finds characters without direct link to user",
    auth=AuthBearer(),
    response={200: List[TokenUserCharacterResponse], 403: ErrorResponse},
)
def characters_without_user(request) -> List[TokenUserCharacterResponse]:
    if not (
        request.user.is_superuser or user_in_team(request.user, TECH_TEAM)
    ):
        return 403, "Not authorised"

    response = []

    for char in EveCharacter.objects.filter(user__isnull=True):
        item = TokenUserCharacterResponse(
            character_id=char.character_id, character_name=char.character_name
        )
        if char and char.token and char.token.user:
            item.token_user_id = char.token.user.id
            item.token_user_name = char.token.user.username

            response.append(item)

    return response


@router.get(
    "/esi_corporation",
    description="Returns ESI details about a corporation",
    auth=AuthBearer(),
    response={200: EsiCorporation, 400: int, 403: str},
)
def esi_corporation(request, corporation_id: int) -> EsiCorporation:
    if not (
        request.user.is_superuser or user_in_team(request.user, TECH_TEAM)
    ):
        return 403, "Not authorised"

    response = EsiClient(None).get_corporation(corporation_id)
    if response.success():
        return response.typed_data
    else:
        return 400, response.response_code
