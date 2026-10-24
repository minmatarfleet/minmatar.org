"""Tell the API a pilot pressed Sitting out on their private fleet invite."""

import requests
from pydantic import BaseModel

from app.settings import settings

FLEETS_BASE_URL = f"{settings.API_URL}/fleets"
AUTH_HEADERS = {"Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}"}


class DiscordSitOutRequest(BaseModel):
    discord_user_id: int


class SitOutError(Exception):
    pass


def sit_out(invite_id: int, discord_user_id: int) -> None:
    response = requests.post(
        f"{FLEETS_BASE_URL}/invites/{invite_id}/discord-out",
        headers=AUTH_HEADERS,
        json=DiscordSitOutRequest(
            discord_user_id=discord_user_id
        ).model_dump(),
        timeout=10,
    )
    if response.status_code >= 400:
        detail = "Request failed"
        try:
            detail = response.json().get("detail") or detail
        except Exception:
            detail = response.text or detail
        raise SitOutError(str(detail))
