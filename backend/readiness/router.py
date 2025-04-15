import logging
from datetime import datetime, timedelta

from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse
from authentication import AuthBearer

from fleets.models import EveFleetInstanceMember

router = Router(tags=["Pilot Readiness and Experience"])

log = logging.getLogger(__name__)


class ReadinessResponse(BaseModel):
    summary: str = ""
    total: int = 0


@router.get(
    "",
    description="Readiness summary",
    auth=AuthBearer(),
    response={
        200: ReadinessResponse,
        403: ErrorResponse,
    },
)
def readiness_summary(request):
    query = EveFleetInstanceMember.objects.filter(
        join_time__gt=datetime.now() - timedelta(days=30)
    )
    return ReadinessResponse(
        summary="Testing",
        total=query.count(),
    )
