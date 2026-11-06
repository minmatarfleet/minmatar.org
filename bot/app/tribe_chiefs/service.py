"""Tell the API the executor answered a chief volunteer from their DM."""

import requests
from pydantic import BaseModel

from app.settings import settings

TRIBES_BASE_URL = f"{settings.API_URL}/tribes"
AUTH_HEADERS = {"Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}"}


class DiscordChiefActionRequest(BaseModel):
    discord_user_id: int


class ChiefActionError(Exception):
    pass


def answer_volunteer(volunteer_id: int, action: str, discord_user_id: int):
    """``action`` is "appoint" or "decline"."""
    response = requests.post(
        f"{TRIBES_BASE_URL}/chief-volunteers/{volunteer_id}/discord-{action}",
        headers=AUTH_HEADERS,
        json=DiscordChiefActionRequest(
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
        raise ChiefActionError(str(detail))
