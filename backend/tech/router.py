import logging
import datetime

from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers import TECH_TEAM, user_in_team

from discord.client import DiscordClient
from fleets.notifications import get_fleet_discord_notification

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
    "/discord_pre_ping",
    description="POC for Discod fleet pre-pings.",
    auth=AuthBearer(),
    response={200: str, 403: ErrorResponse},
)
def discord_fleet_pre_ping(request):
    if not (
        request.user.is_superuser or user_in_team(request.user, TECH_TEAM)
    ):
        return 403, ErrorResponse(
            "Only admins and tech team members can access this endpoint."
        )

    payload = get_fleet_discord_notification(
        is_pre_ping=True,
        content="Everyone",
        fleet_id=99999,
        fleet_type="NON STRATEGIC OPERATION",
        fleet_location="Sosala",
        fleet_audience="Tech Team",
        fleet_commander_name="Silvatek",
        fleet_commander_id=2119722788,
        fleet_description="Testing pre-pings",
        fleet_voice_channel="Testing",
        fleet_voice_channel_link="https://my.minmatar.org/",
        fleet_start_time=datetime.datetime.now(),
    )

    discord = DiscordClient()

    discord.create_message(
        "1174095095537078312",
        payload=payload,
    )

    return "Success"
