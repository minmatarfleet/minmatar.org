from pydantic import BaseModel
from app.settings import settings

API_URL = settings.API_URL
STANDING_URL = f"{API_URL}/standingfleet/voicetracking"


class CreateStandingFleetTrackingRequest(BaseModel):
    minutes: int
    usernames: list[str]


class StandingFleetTrackingResponse(BaseModel):
    ids: list[int]
