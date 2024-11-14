from pydantic import BaseModel

API_URL = "https://api.minmatar.org/api"
STANDING_URL = f"{API_URL}/standingfleet/voicetracking"


class CreateStandingFleetTrackingRequest(BaseModel):
    minutes: int
    usernames: list[str]


class StandingFleetTrackingResponse(BaseModel):
    ids: list[int]
