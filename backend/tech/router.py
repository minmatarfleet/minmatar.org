import logging

from ninja import Router

from django.conf import settings
from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers import TECH_TEAM, user_in_team
from eveonline.client import EsiClient

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


@router.get(
    "character/{int:character_id}",
    summary="ESI debugging without token",
    auth=AuthBearer(),
    response={
        200: str,
        403: ErrorResponse,
    },
)
def debug_character_esi(request, character_id: int):
    """API endpoint for exploring the ESI client"""
    if not (
        request.user.is_superuser or user_in_team(request.user, TECH_TEAM)
    ):
        return 403, ErrorResponse(detail="Not authorised")

    response = EsiClient(None).get_character_public_data(character_id)
    if response.success():
        char = response.results()
        return char["name"]
    else:
        return f"Error {response.response_code}, {response.response}"


@router.get(
    "character/{int:character_id}/skills",
    summary="ESI debugging with token",
    auth=AuthBearer(),
    response={
        200: str,
        403: ErrorResponse,
    },
)
def debug_skills_esi(request, character_id: int):
    if not (
        request.user.is_superuser or user_in_team(request.user, TECH_TEAM)
    ):
        return 403, ErrorResponse(detail="Not authorised")

    response = EsiClient(character_id).get_character_skills()
    if response.success():
        skills = response.results()
        return str(len(skills))
    else:
        return f"Error {response.response_code}, {response.response}"
