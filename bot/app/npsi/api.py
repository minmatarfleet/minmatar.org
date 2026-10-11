from pydantic import BaseModel

from app.settings import settings

NPSI_BASE_URL = f"{settings.API_URL}/fleets"


class DiscordNpsiActionRequest(BaseModel):
    discord_user_id: int


class DiscordNpsiActionResponse(BaseModel):
    event_id: int
    status: str
    fleet_id: int | None = None
