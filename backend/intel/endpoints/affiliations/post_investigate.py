"""POST /entities/{kind}/{eve_id}/investigate - jump the queue."""

from __future__ import annotations

from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer
from intel.affiliations.constants import MANUAL_PRIORITY
from intel.affiliations.names import names_for
from intel.endpoints.affiliations.common import (
    FORBIDDEN,
    can_manage,
    endpoint,
    entity_ref,
)
from intel.endpoints.affiliations.schemas import InvestigateResponse
from intel.models import IntelEntity


@endpoint(
    "post",
    "/{kind}/{int:eve_id}/investigate",
    summary="Queue a group's investigation ahead of everything else",
    auth=AuthBearer(),
    response={
        200: InvestigateResponse,
        400: ErrorResponse,
        403: ErrorResponse,
    },
)
def post_investigate(request, kind: str, eve_id: int):
    if not can_manage(request.user):
        return 403, ErrorResponse(detail=FORBIDDEN)
    if kind not in (IntelEntity.Kind.ALLIANCE, IntelEntity.Kind.CORPORATION):
        return 400, ErrorResponse(detail="Only groups are investigated.")
    entity, _ = IntelEntity.objects.get_or_create(kind=kind, eve_id=eve_id)
    if not entity.name:
        entity.name = names_for([eve_id]).get(eve_id, "")
    if entity.status != IntelEntity.Status.INVESTIGATING:
        entity.status = IntelEntity.Status.QUEUED
        entity.queued_at = timezone.now()
    entity.priority = max(entity.priority, MANUAL_PRIORITY)
    entity.save()
    return InvestigateResponse(
        **entity_ref(entity), status=entity.status, priority=entity.priority
    )
