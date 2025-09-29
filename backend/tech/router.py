import logging
import json
import time
from datetime import timedelta, datetime

from ninja import Router
from typing import List, Optional

from django.contrib.auth.models import User
from django.conf import settings
from django.db.models import Count, F
from django.http import HttpResponse
from django.utils import timezone
from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from discord.client import DiscordClient
from discord.models import DiscordUser
from discord.tasks import sync_discord_user, sync_discord_nickname
from discord.helpers import remove_all_roles_from_guild_member
from groups.helpers import TECH_TEAM, user_in_team
from groups.tasks import update_affiliation
from eveonline.client import esi_for
from eveonline.models import EveCharacter, EvePlayer
from eveonline.tasks import update_character_assets, update_character_skills
from fleets.models import EveFleetAudience, EveFleet
from structures.tasks import send_discord_structure_notification
from structures.models import EveStructurePing
from fittings.models import EveFitting
from tech.docker import (
    get_containers,
    container_names,
    sort_chronologically,
    DockerContainer,
    DockerLogQuery,
    DockerLogEntry,
)
from tech.dbviews import create_all_views
from reddit.client import RedditClient


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
    deprecated=True,
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


class TestFleetCreationRequest(BaseModel):
    """Request to create a test fleet"""

    description: Optional[str] = "Technical test fleet"
    type: Optional[str] = "training"
    start_tracking: Optional[bool] = False
    disable_motd: Optional[bool] = True
    start_time: Optional[datetime] = None


@router.post(
    "/make_test_fleet",
    summary="Create a hidden test fleet",
    auth=AuthBearer(),
    response={200: int, 403: ErrorResponse, 404: ErrorResponse},
)
def make_test_fleet(request, data: TestFleetCreationRequest):
    if not permitted(request.user):
        return 403, ErrorResponse(detail="Not authorised")

    hidden_audience = EveFleetAudience.objects.filter(hidden=True).first()
    if not hidden_audience:
        return 404, ErrorResponse.log(detail="No hidden audience found")

    if data.start_time is None:
        data.start_time = timezone.now()

    fleet = EveFleet.objects.create(
        audience=hidden_audience,
        description=data.description,
        type=data.type,
        start_time=data.start_time,
        created_by=request.user,
        disable_motd=data.disable_motd,
    )

    if data.start_tracking:
        fleet.start()

    logger.info("Test fleet %d created by %s", fleet.id, request.user.username)

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
    query.abort_after(timedelta(seconds=5))

    all_logs: List[DockerLogEntry] = []

    for container in get_containers(container_match):
        logger.info("Get logs, fetching %s", container.name)
        container_logs = DockerContainer(container).log_entries(query)
        all_logs += container_logs

    if query.aborted():
        logger.warning("Get logs, query aborted")

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


class StructureNotificationResponse(BaseModel):
    """Response model for structure notification API"""

    id: int
    type: str
    summary: str
    timestamp: datetime


@router.get(
    "/notifications/{int:character_id}",
    summary="Get character notifications",
    auth=AuthBearer(),
    response={
        200: List[StructureNotificationResponse],
        400: ErrorResponse,
        403: ErrorResponse,
    },
)
def get_notifications(request, character_id: int):
    if not permitted(request.user):
        return 403, "Not authorised"

    response = esi_for(character_id).get_character_notifications()

    if not response.success():
        return 400, ErrorResponse(detail=str(response.response))

    combat_types = [
        "StructureDestroyed",
        "StructureLostArmor",
        "StructureLostShields",
        "StructureUnderAttack",
    ]

    results = []
    for notification in response.results():
        if notification["type"] in combat_types:
            results.append(
                StructureNotificationResponse(
                    id=notification["notification_id"],
                    type=notification["type"],
                    timestamp=notification["timestamp"],
                    summary=notification["text"],
                )
            )

    return results


@router.post(
    "/discordping",
    summary="Get character notifications",
    auth=AuthBearer(),
    response={
        200: None,
        404: ErrorResponse,
        403: ErrorResponse,
    },
)
def discord_ping(request, notification_id: int, channel_id: int):
    if not permitted(request.user):
        return 403, "Not authorised"

    event = EveStructurePing.objects.filter(
        notification_id=notification_id,
    ).first()
    if not event:
        return 404, ErrorResponse(detail="Event not found")

    send_discord_structure_notification(event, channel_id)


class CharacterFlagResponse(BaseModel):
    """Response model for character flags"""

    character_id: int
    character_name: str = ""
    flags: List[str] = []
    token_count: int = 0
    scope_count: int = 0
    tag_count: int = 0
    corp_name: str | None = None
    alliance_name: str | None = None


@router.get(
    "/character_flags",
    summary="Proof-of-concept for returning character flags",
    auth=AuthBearer(),
    response={
        200: List[CharacterFlagResponse],
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def character_flags(request):
    if not permitted(request.user):
        return 403, ErrorResponse(detail="Not authorised")

    chars = EveCharacter.objects.filter(user=request.user).annotate(
        token_count=Count("token", distinct=True),
        scope_count=Count("token__scopes", distinct=True),
        tag_count=Count("evecharactertag", distinct=True),
        corp_name=F("corporation__name"),
        alliiance_name=F("alliance__name"),
    )

    response = []
    for char in chars:
        flags = []
        if char.token_count == 0:
            flags.append("NO_TOKENS")
        if char.token_count > 1:
            flags.append("MULTIPLE_TOKENS")
        if char.esi_suspended:
            flags.append("ESI_SUSPENDED")
        if char.tag_count == 0:
            flags.append("NO_TAGS")
        flags.sort()
        response.append(
            CharacterFlagResponse(
                character_id=char.character_id,
                character_name=char.character_name,
                corp_name=char.corp_name,
                token_count=char.token_count,
                scope_count=char.scope_count,
                tag_count=char.tag_count,
                flags=flags,
            )
        )
    return response


@router.get(
    "/errortest",
    summary="Test error handling",
    response={200: None, 400: ErrorResponse},
)
def test_error_id(request):
    err = ErrorResponse.new(detail="Fake error")
    logger.error("Fake error for testing (%s): %s", err.id, err.detail)
    return 400, err


class AssetSummary(BaseModel):
    """Summary of assets"""

    count: int
    total: int
    quantity: int
    elapsed_time: float


@router.get(
    "/assets",
    summary="Character asset summary",
    auth=AuthBearer(),
    response={200: AssetSummary, 403: ErrorResponse, 404: ErrorResponse},
)
def asset_summary(
    request,
    character_id: int,
    type_id: Optional[int] = None,
    location_id: Optional[int] = None,
    location_flag: Optional[str] = None,
    fl33t_fittings: Optional[bool] = False,
    refresh_char: Optional[bool] = False,
):
    if not permitted(request.user):
        return 403, ErrorResponse(detail="Not authorised")

    char = EveCharacter.objects.filter(character_id=character_id).first()
    if not char:
        return 404, ErrorResponse(detail="Character not found")
    if not char.assets_json:
        return 404, ErrorResponse(detail="Character has no assets")

    if refresh_char:
        update_character_assets.apply_async(args=[character_id])

    start = time.perf_counter()

    fitting_ids = []
    if fl33t_fittings:
        for fitting in EveFitting.objects.all():
            fitting_ids.append(fitting.ship_id)

    found = 0
    quantity = 0
    assets = json.loads(char.assets_json)
    for asset in assets:
        if type_id and type_id != asset["type_id"]:
            continue
        if location_id and location_id != asset["location_id"]:
            continue
        if location_flag and location_flag != asset["location_flag"]:
            continue
        if fl33t_fittings and asset["type_id"] not in fitting_ids:
            continue
        found += 1
        quantity += asset["quantity"]

    data = AssetSummary(
        elapsed_time=time.perf_counter() - start,
        total=len(assets),
        count=found,
        quantity=quantity,
    )

    return 200, data


@router.get(
    "/discordroles",
    summary="Get Discord role details",
    auth=AuthBearer(),
    response={200: str, 403: ErrorResponse},
)
def discord_roles(request):
    if not permitted(request.user):
        return 403, ErrorResponse(detail="Not authorised")

    return json.dumps(DiscordClient().get_roles())


@router.get(
    "/force_refresh",
    summary="Force a full player / character refresh",
    auth=AuthBearer(),
    response={200: List[str], 403: ErrorResponse, 404: ErrorResponse},
)
def force_refresh(request, username: str):
    """
    Force a full player & character data refresh.
    """

    if not permitted(request.user):
        return 403, ErrorResponse(detail="Not authorised")

    logger.info("Full refresh requested for user %s", username)

    response = []

    user = User.objects.filter(username=username).first()
    if user is None:
        return 404, ErrorResponse.log(
            "User not found, cannot refresh", f"User not found: {username}"
        )

    response.append(f"User {username} found, ID = {user.id}")

    discord = DiscordUser.objects.filter(user=user).first()
    if discord:
        response.append(f"DiscordUser found for user, id = {discord.id}")
    else:
        response.append(f"No DiscordUser found for {username}")

    player = EvePlayer.objects.filter(user=user).first()
    if player:
        response.append(
            f"Player found for user, primary = {player.primary_character}"
        )
    else:
        player = EvePlayer.objects.create(
            user=user,
        )
        response.append(f"Player found for {username}")

    update_affiliation(user.id)
    response.append(f"Updated affiliations for {username}")

    sync_discord_user(user.id)
    response.append(f"Synced Discord roles for {username}")

    sync_discord_nickname(user.id, True)
    response.append(f"Synced Discord nickname for {username}")

    characters = EveCharacter.objects.filter(user=user)
    if characters.count() == 0:
        response.append(f"No characters found for {username}")

    for char in characters:
        response.append(
            f"Found character {char.character_name} ({char.character_id})"
        )

        update_character_assets(char.character_id)
        response.append(
            f"  Updated assets for character {char.character_name}"
        )

        update_character_skills(char.character_id)
        response.append(
            f"  Updated skills for character {char.character_name}"
        )

    response.append("Complete.")

    logger.info("Full refresh complete for %s", username)

    return response


@router.post(
    "/remove_discord_roles",
    summary="Remove all roles from a discord user on a discord server",
    auth=AuthBearer(),
    response={
        200: None,
        403: ErrorResponse,
        409: ErrorResponse,
    },
)
def remove_discord_roles(request, user_id: int):
    if not permitted(request.user):
        return 403, ErrorResponse(detail="Not authorised")

    try:
        remove_all_roles_from_guild_member(user_id)
    except ValueError as e:
        return 409, ErrorResponse(detail=str(e))
    return 200, None


@router.get(
    "/reddit_test",
    summary="Test calling the Reddit API",
    auth=AuthBearer(),
    response={200: str, 403: ErrorResponse},
)
def reddit_test(request):
    """
    Test of the Reddit API
    """

    if not permitted(request.user):
        return 403, ErrorResponse(detail="Not authorised")

    logger.info("Reddit API test")

    return 200, RedditClient().get_my_details()["icon_img"]
