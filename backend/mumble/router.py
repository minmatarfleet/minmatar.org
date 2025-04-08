from django.conf import settings
from ninja import Router
from pydantic import BaseModel

from authentication import AuthBearer
from eveonline.helpers.characters import user_primary_character

from .models import MumbleAccess

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
    response={200: MumbleConnectionInformationResponse, 403: ErrorResponse},
)
def get_mumble_connection(request):
    if not request.user.has_perm("mumble.view_mumbleaccess"):
        return 403, {"detail": "You do not have permission to access mumble."}

    primary_character = user_primary_character(request.user)
    if not primary_character:
        return 404, {"detail": "Primary character not found."}

    # if not EvePrimaryCharacter.objects.filter(
    #     character__token__user=request.user
    # ).exists():
    #     return 404, {"detail": "Primary character not found."}

    mumble_access, _ = MumbleAccess.objects.get_or_create(user=request.user)

    # primary_character = EvePrimaryCharacter.objects.get(
    #     character__token__user=request.user
    # ).character

    response = {
        "username": primary_character.character_name,
        "password": mumble_access.password,
        "url": f"mumble://{primary_character.character_name}:{mumble_access.password}@{settings.MUMBLE_MURMUR_HOST}:{settings.MUMBLE_MURMUR_PORT}",  # noqa
    }

    return response
