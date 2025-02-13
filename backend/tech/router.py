import logging

from ninja import Router

# from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer
from groups.helpers import TECH_TEAM, user_in_team

from discord.client import DiscordClient

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

    payload = {
        "content": "@here",
        "components": [
            {
                "type": 1,
                "components": [
                    {
                        "style": 5,
                        "label": "View Fleet Information",
                        "url": "https://my.minmatar.org/fleets/history/0",
                        "disabled": False,
                        "type": 2,
                    },
                    {
                        "style": 5,
                        "label": "New Player Instructions",
                        "url": "https://minmatar.org/guides/new-player-fleet-guide/",
                        "disabled": False,
                        "type": 2,
                    },
                ],
            }
        ],
        "embeds": [
            {
                "type": "rich",
                "title": "TEST PRE+PING",
                "description": "Testing of fleet pre-pings",
                "color": 0x18ED09,
                "author": {
                    "name": "Silvatek",
                    "icon_url": "https://images.evetech.net/characters/2119722788/portrait?size=32",
                },
                "url": "https://my.minmatar.org/",
                "footer": {
                    "text": "Minmatar Fleet FC Team",
                    "icon_url": "https://minmatar.org/wp-content/uploads/2023/04/Logo13.png",
                },
            }
        ],
    }

    discord = DiscordClient()

    discord.create_message(
        "1174095095537078312",
        payload=payload,
    )

    return "Success"
