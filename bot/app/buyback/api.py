from pydantic import BaseModel

from app.settings import settings

BUYBACK_BASE_URL = f"{settings.API_URL}/buyback/stock"


class DiscordAckRequest(BaseModel):
    discord_user_id: int
    action: str


class DiscordAckResponse(BaseModel):
    id: int
    status: str
