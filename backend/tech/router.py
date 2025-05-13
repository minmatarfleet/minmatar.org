import logging
from datetime import datetime, timedelta

from ninja import Router
from typing import List, Optional

from django.conf import settings
from django.http import HttpResponse
from pydantic import BaseModel
from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers import TECH_TEAM, user_in_team
from eveonline.helpers.characters import user_characters
from eveonline.models import EveCharacter
from eveonline.client import EsiClient
from tech.docker import (
    container_names,
    sort_chronologically,
    DockerContainer,
    DockerLogQuery,
    DockerLogEntry,
)

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
    "/fleet_tracking_poc",
    summary="Proof-of-concept for advanced fleet tracking",
    auth=AuthBearer(),
    response={200: List[int], 403: ErrorResponse, 404: ErrorResponse},
)
def fleet_tracking_poc(request):
    if not (
        request.user.is_superuser or user_in_team(request.user, TECH_TEAM)
    ):
        return 403, ErrorResponse(detail="Not authorised")

    # Find a fleet that one of the user's characters is in
    esi_fleet = None
    for char in user_characters(request.user):
        fleet_response = EsiClient(char).get_active_fleet()
        if fleet_response.success():
            esi_fleet = fleet_response.data
            if esi_fleet["fleet_boss_id"] == char.id:
                # Don't look further if is fleet boss
                break
            if esi_fleet["role"] == "fleet_commander":
                # Don't look further if is fleet commander
                break

    if not esi_fleet:
        return 404, ErrorResponse(detail="No characters in fleet")

    fleet_id = esi_fleet["fleet_id"]
    fleet_boss_id = esi_fleet["fleet_boss_id"]

    # Find the character that is boss
    boss_char = EveCharacter.objects.filter(character_id=fleet_boss_id).first()

    if not boss_char:
        return 404, ErrorResponse(detail="Fleet boss character not found")

    member_response = EsiClient(boss_char).get_fleet_members(fleet_id)

    fleet_members = []

    for member in member_response.results():
        fleet_members.append(member["character_id"])

    return 200, fleet_members


@router.get(
    "/containers",
    summary="List all Docker containers",
    auth=AuthBearer(),
    response={200: List[str], 403: ErrorResponse},
)
def list_containers(request):
    if not (
        request.user.is_superuser or user_in_team(request.user, TECH_TEAM)
    ):
        return 403, "Not authorised"

    # client = docker.DockerClient(base_url="unix://var/run/docker.sock")
    # containers = client.containers.list()
    # return [container.name for container in containers]
    return container_names()


@router.get(
    "/containers/{container_match}/logs",
    summary="Get historic logs for a Docker container",
    description="Specify a time delta (how long ago to start reading logs from) "
    "and duration (how long to include logs for from that point) in minutes, "
    "as well as the name of the container. ",
    auth=AuthBearer(),
    response={200: str, 403: ErrorResponse},
)
def get_logs(
    request,
    container_match: str,
    start_delta_mins: int = 20,
    duration_mins: Optional[int] = None,
    search_for: Optional[str] = None,
):
    if not (
        request.user.is_superuser or user_in_team(request.user, TECH_TEAM)
    ):
        return 403, "Not authorised"

    now = datetime.now()
    start_time = now - timedelta(minutes=start_delta_mins)
    if not duration_mins:
        duration_mins = max(start_delta_mins, 60)
    end_time = start_time + timedelta(minutes=duration_mins)

    query = DockerLogQuery(
        containers=container_match,
        start_time=start_time,
        end_time=end_time,
        search_for=search_for,
    )

    all_logs: List[DockerLogEntry] = []

    for container_name in container_names():
        if container_name.startswith("tools"):
            # Skip containers from old "tools" site
            logger.debug("Get logs, skipping %s", container_name)
            continue
        if container_match in container_name:
            logger.info("Get logs, fetching %s", container_name)
            container_logs = DockerContainer(container_name).log_entries(query)
            all_logs += container_logs

    logger.info("Get logs, sorting %d entries", len(all_logs))

    sort_chronologically(all_logs)

    logger.info("Get logs, building response")

    response = ""
    for log_entry in all_logs:
        response += str(log_entry) + "\n"

    logger.info("Get logs, complete.")

    return HttpResponse(response, content_type="text/plain")


# @router.get(
#     "/logs/{container_name}",
#     summary="Stream logs for a specific container",
#     auth=AuthBearer(),
#     response={200: str, 403: ErrorResponse},
# )
# def stream_logs(request, container_name: str):
#     if not (
#         request.user.is_superuser or user_in_team(request.user, TECH_TEAM)
#     ):
#         return 403, "Not authorised"

#     client = docker.DockerClient(base_url="unix://var/run/docker.sock")
#     container = client.containers.get(container_name)

#     def event_stream():
#         for log in container.logs(stream=True, stdout=True, stderr=True):
#             yield f"data: {log.decode('utf-8')}\n\n"

#     return StreamingHttpResponse(
#         event_stream(), content_type="text/event-stream"
#     )
