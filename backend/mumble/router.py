from typing import List

from ninja import Router
from pydantic import BaseModel
from django.conf import settings

from authentication import AuthBearer

from .models import MumbleAccess
from eveonline.models import EvePrimaryCharacter

router = Router(tags=["Mumble"])


class MumbleConnectionInformationResponse(BaseModel):
    username: str
    password: str
    url: str


class ErrorResponse(BaseModel):
    detail: str


@router.get(
    "/connection",
    summary="Get mumble connection information",
    auth=AuthBearer(),
    response={200: MumbleConnectionInformationResponse, 404: ErrorResponse},
)
def get_mumble_connection(request):
    if not MumbleAccess.objects.filter(user=request.user).exists():
        return 404, {"detail": "Mumble access not found."}

    if not EvePrimaryCharacter.objects.filter(character__token__user=request.user).exists():
        return 404, {"detail": "Primary character not found."}

    mumble_access = MumbleAccess.objects.get(user=request.user)

    primary_character = EvePrimaryCharacter.objects.get(character__token__user=request.user).character

    response = {
        "username": primary_character.character_name,
        "password": mumble_access.password,
        "url": "mumble://{0}:{1}@{2}:{3}".format(primary_character.character_name, mumble_access.password, settings.MUMBLE_MURMUR_HOST, settings.MUMBLE_MURMUR_PORT),
    }

    return response