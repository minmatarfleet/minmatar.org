import requests

from app.settings import settings

from .api import LOYALTY_BASE_URL, DiscordAckRequest, DiscordAckResponse

AUTH_HEADERS = {"Authorization": f"Bearer {settings.MINMATAR_API_TOKEN}"}


class DiscordAckError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def discord_ack_order(
    order_id: int, *, action: str, discord_user_id: int
) -> DiscordAckResponse:
    response = requests.post(
        f"{LOYALTY_BASE_URL}/orders/{order_id}/discord-ack",
        headers=AUTH_HEADERS,
        json=DiscordAckRequest(
            discord_user_id=discord_user_id,
            action=action,
        ).model_dump(),
        timeout=10,
    )
    if response.status_code >= 400:
        detail = "Request failed"
        try:
            detail = response.json().get("detail") or detail
        except Exception:
            detail = response.text or detail
        raise DiscordAckError(str(detail), status_code=response.status_code)
    return DiscordAckResponse.model_validate(response.json())
