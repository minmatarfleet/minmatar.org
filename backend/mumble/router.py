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


def mumble_username(user) -> str:
    primary = user_primary_character(user)
    if primary:
        return "[FLEET] " + primary.character_name

    return "[?????] " + user.username


@router.get(
    "/connection",
    summary="Get mumble connection information",
    auth=AuthBearer(),
    response={
        200: MumbleConnectionInformationResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def get_mumble_connection(request):
    if not request.user.has_perm("mumble.view_mumbleaccess"):
        return 403, {"detail": "You do not have permission to access mumble."}

    primary_character = user_primary_character(request.user)
    if not primary_character:
        return 404, {"detail": "Primary character not found."}

    mumble_access, _ = MumbleAccess.objects.get_or_create(
        user=request.user,
        defaults={"username": mumble_username(request.user)},
    )

    if mumble_access.suspended:
        return 400, ErrorResponse(detail="Mumble access suspended")

    if not mumble_access.username:
        mumble_access.username = mumble_username(request.user)
        mumble_access.save()

    response = {
        "username": mumble_access.username,
        "password": mumble_access.password,
        "url": f"mumble://{primary_character.character_name}:{mumble_access.password}@{settings.MUMBLE_MURMUR_HOST}:{settings.MUMBLE_MURMUR_PORT}",  # noqa
    }

    return response
