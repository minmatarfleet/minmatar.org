import logging
from datetime import timedelta

from ninja import Router
from typing import List, Optional

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers import TECH_TEAM, user_in_team
from fleets.models import EveFleetAudience, EveFleet
from tech.docker import (
    container_names,
    sort_chronologically,
    DockerContainer,
    DockerLogQuery,
    DockerLogEntry,
)
from tech.dbviews import create_all_views

router = Router(tags=["Tech"])
logger = logging.getLogger(__name__)


def permitted(user) -> bool:
    return user.is_superuser or user_in_team(user, TECH_TEAM)


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
    if not permitted(request.user):
        return 403, "Not authorised"
    if hasattr(settings, var_name):
        return "Set"
    else:
        return "Not set"


@router.get(
    "/fleet_tracking_poc",
    summary="Proof-of-concept for advanced fleet tracking",
    auth=AuthBearer(),
    response={200: int, 403: ErrorResponse, 404: ErrorResponse},
)
def fleet_tracking_poc(
    request, fleet_id: Optional[int] = None, start: bool = False
):
    if not permitted(request.user):
        return 403, ErrorResponse(detail="Not authorised")

    if fleet_id:
        fleet = EveFleet.objects.get(id=fleet_id)
    else:
        audience = EveFleetAudience.objects.filter(hidden=True).first()
        if not audience:
            return 404, ErrorResponse(detail="No hidden audience found")
        fleet = EveFleet.objects.create(
            audience=audience,
            description="Technical test fleet",
            type="training",
            start_time=timezone.now(),
            created_by=request.user,
            disable_motd=True,
        )

    if start:
        fleet.start()

    return 200, fleet.id


@router.get(
    "/containers",
    summary="List all Docker containers",
    auth=AuthBearer(),
    response={200: List[str], 403: ErrorResponse},
)
def list_containers(request):
    if not permitted(request.user):
        return 403, "Not authorised"

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
    if not permitted(request.user):
        return 403, "Not authorised"

    now = timezone.now()
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


@router.get(
    "/dbviews",
    summary="(Re)create database views",
    auth=AuthBearer(),
    response={200: None, 403: ErrorResponse},
)
def create_db_views(request):
    if not permitted(request.user):
        return 403, "Not authorised"

    create_all_views()

    return 200, None
