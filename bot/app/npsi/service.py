import requests

from app.settings import settings

from .api import (
    NPSI_BASE_URL,
    DiscordNpsiActionRequest,
    DiscordNpsiActionResponse,
)

AUTH_HEADERS = {"Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}"}


class NpsiDiscordActionError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _post_action(
    path: str, event_id: int, discord_user_id: int
) -> DiscordNpsiActionResponse:
    response = requests.post(
        f"{NPSI_BASE_URL}{path}",
        headers=AUTH_HEADERS,
        json=DiscordNpsiActionRequest(
            discord_user_id=discord_user_id
        ).model_dump(),
        timeout=15,
    )
    if response.status_code >= 400:
        detail = "Request failed"
        try:
            detail = response.json().get("detail") or detail
        except Exception:
            detail = response.text or detail
        raise NpsiDiscordActionError(
            str(detail), status_code=response.status_code
        )
    return DiscordNpsiActionResponse.model_validate(response.json())


def post_to_schedule(
    event_id: int, *, discord_user_id: int
) -> DiscordNpsiActionResponse:
    return _post_action(
        f"/npsi-events/{event_id}/discord-create",
        event_id,
        discord_user_id,
    )


def send_preping(
    event_id: int, *, discord_user_id: int
) -> DiscordNpsiActionResponse:
    return _post_action(
        f"/npsi-events/{event_id}/discord-preping",
        event_id,
        discord_user_id,
    )


def start_tracking(
    event_id: int, *, discord_user_id: int
) -> DiscordNpsiActionResponse:
    return _post_action(
        f"/npsi-events/{event_id}/discord-tracking",
        event_id,
        discord_user_id,
    )
