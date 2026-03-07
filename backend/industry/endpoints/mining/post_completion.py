"""POST "{system_id}/completion" - record a mining anomaly completion."""

from datetime import timedelta

from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer
from industry.endpoints.mining.schemas import (
    MINING_LEVEL_DURATION_MINUTES,
    PostCompletionRequest,
    PostCompletionResponse,
)
from industry.models import MiningUpgradeCompletion
from sovereignty.services import (
    get_mining_level_for_system,
    get_mining_systems_queryset,
)

PATH = "{int:system_id}/completion"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Record a mining upgrade completion for a system",
    "auth": AuthBearer(),
    "response": {
        200: PostCompletionResponse,
        400: ErrorResponse,
        404: ErrorResponse,
    },
}


def post_completion(request, system_id: int, payload: PostCompletionRequest):
    systems_qs = get_mining_systems_queryset()
    config = systems_qs.filter(system_id=system_id).first()
    if not config:
        return 404, ErrorResponse(
            detail=f"System {system_id} is not a registered mining system."
        )
    system_name = config.system_name or str(system_id)
    level = get_mining_level_for_system(system_id)
    if level is None:
        return 400, ErrorResponse(
            detail=f"System {system_id} has no mining upgrade level."
        )
    completed_at = (
        payload.completed_at if payload.completed_at else timezone.now()
    )
    MiningUpgradeCompletion.objects.create(
        system_id=system_id,
        system_name=system_name,
        completed_at=completed_at,
        completed_by=request.user,
    )
    duration_min = MINING_LEVEL_DURATION_MINUTES.get(level, 60)
    next_available_at = completed_at + timedelta(minutes=duration_min)
    return 200, PostCompletionResponse(
        system_id=system_id,
        system_name=system_name,
        mining_upgrade_level=level,
        last_completion=completed_at,
        next_available_at=next_available_at,
    )
