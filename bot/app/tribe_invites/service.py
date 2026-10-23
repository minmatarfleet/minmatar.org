"""Tell the API a pilot pressed Decline on their tribe invite DM."""

import requests
from pydantic import BaseModel

from app.settings import settings

TRIBES_BASE_URL = f"{settings.API_URL}/tribes"
AUTH_HEADERS = {"Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}"}


class DiscordDeclineRequest(BaseModel):
    discord_user_id: int


class DeclineError(Exception):
    pass


def decline_invitation(invitation_id: int, discord_user_id: int) -> None:
    response = requests.post(
        f"{TRIBES_BASE_URL}/invitations/{invitation_id}/discord-decline",
        headers=AUTH_HEADERS,
        json=DiscordDeclineRequest(
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
        raise DeclineError(str(detail))
