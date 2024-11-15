from ninja import Router
from pydantic import BaseModel

from authentication import AuthBearer
from standingfleet.models import StandingFleetVoiceRecord

router = Router(tags=["Standing Fleet"])


class CreateStandingFleetTrackingRequest(BaseModel):
    minutes: int
    usernames: list[str]


class StandingFleetTrackingResponse(BaseModel):
    ids: list[int]


@router.post(
    "/voicetracking",
    response=StandingFleetTrackingResponse,
    auth=AuthBearer(),
)
def create_tracking(request, payload: CreateStandingFleetTrackingRequest):
    records = []
    for username in payload.usernames:
        record = StandingFleetVoiceRecord.objects.create(
            username=username, minutes=payload.minutes
        )
        records.append(record.id)
    return {"ids": records}
