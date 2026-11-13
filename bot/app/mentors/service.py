"""Tell the API what a pilot pressed on a mentor class DM."""

import requests
from pydantic import BaseModel

from app.settings import settings

MENTORS_BASE_URL = f"{settings.API_URL}/learning/mentors"
AUTH_HEADERS = {
    "Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}",  # pragma: allowlist secret
}


class MentorActionError(Exception):
    pass


class ActionBody(BaseModel):
    discord_user_id: int


class FeedbackBody(BaseModel):
    discord_user_id: int
    answer: str
    note: str = ""


def _post(path: str, body: BaseModel) -> str:
    response = requests.post(
        f"{MENTORS_BASE_URL}{path}",
        headers=AUTH_HEADERS,
        json=body.model_dump(),
        timeout=15,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if response.status_code >= 400:
        raise MentorActionError(str(payload.get("detail") or "Request failed"))
    return str(payload.get("message") or "Done.")


def act(request_id: int, action: str, discord_user_id: int) -> str:
    """action: pass, cancel or confirm."""
    return _post(
        f"/requests/{int(request_id)}/discord-{action}",
        ActionBody(discord_user_id=discord_user_id),
    )


def send_feedback(request_id: int, discord_user_id: int, answer: str, note: str) -> str:
    return _post(
        f"/requests/{int(request_id)}/discord-feedback",
        FeedbackBody(discord_user_id=discord_user_id, answer=answer, note=note),
    )
