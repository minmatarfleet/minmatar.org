import logging
import docker
from datetime import datetime, timedelta

from ninja import Router
from typing import List, Optional

from django.conf import settings
from django.http import StreamingHttpResponse
from pydantic import BaseModel
from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers import TECH_TEAM, user_in_team
from eveonline.models import EveCharacter
from tech.docker import docker_containers, DockerContainer

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

    client = docker.DockerClient(base_url="unix://var/run/docker.sock")
    containers = client.containers.list()
    return [container.name for container in containers]


@router.get(
    "/containers/{container_name}/logs",
    summary="Get historic logs for a Docker container",
    description="Specify a time delta (how long ago to start reading logs from) "
    "and duration (how long to include logs for from that point) in minutes, "
    "as well as the name of the container. ",
    auth=AuthBearer(),
    response={200: str, 403: ErrorResponse},
)
def get_logs(
    request,
    container_name: str,
    start_delta_mins: int = 20,
    duration_mins: int = 20,
):
    if not (
        request.user.is_superuser or user_in_team(request.user, TECH_TEAM)
    ):
        return 403, "Not authorised"

    start_time = datetime.now() - timedelta(minutes=start_delta_mins)
    end_time = start_time + timedelta(minutes=duration_mins)

    all_logs = ""

    for container in docker_containers():
        if container_name in container:
            container_logs = DockerContainer(container_name).logs(
                start_time, end_time
            )
            # all_logs = all_logs + "\n" + container_logs
            all_logs = container_logs

    print("[" + all_logs + "]")
    return all_logs


@router.get(
    "/logs/{container_name}",
    summary="Stream logs for a specific container",
    auth=AuthBearer(),
    response={200: str, 403: ErrorResponse},
)
def stream_logs(request, container_name: str):
    if not (
        request.user.is_superuser or user_in_team(request.user, TECH_TEAM)
    ):
        return 403, "Not authorised"

    client = docker.DockerClient(base_url="unix://var/run/docker.sock")
    container = client.containers.get(container_name)

    def event_stream():
        for log in container.logs(stream=True, stdout=True, stderr=True):
            yield f"data: {log.decode('utf-8')}\n\n"

    return StreamingHttpResponse(
        event_stream(), content_type="text/event-stream"
    )
