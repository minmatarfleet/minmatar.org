"""POST /affiliations/{affiliation_id}/decision - confirm or reject one."""

from __future__ import annotations

from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer
from intel.affiliations import resolve
from intel.endpoints.affiliations.common import (
    FORBIDDEN,
    affiliation_out,
    affiliations_query,
    can_manage,
    endpoint,
)
from intel.endpoints.affiliations.schemas import (
    AffiliationSchema,
    DecisionRequest,
)
from intel.models import IntelAffiliation, IntelBloc


@endpoint(
    "post",
    "/{int:affiliation_id}/decision",
    summary="Confirm or reject an affiliation",
    description=(
        "Confirming can also correct the relation or move it to another "
        "bloc. A rejection is remembered: scoring never suggests it again."
    ),
    auth=AuthBearer(),
    response={
        200: AffiliationSchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def post_affiliation_decision(
    request, affiliation_id: int, payload: DecisionRequest
):
    if not can_manage(request.user):
        return 403, ErrorResponse(detail=FORBIDDEN)
    row = affiliations_query().filter(pk=affiliation_id).first()
    if row is None:
        return 404, ErrorResponse(detail="No such affiliation.")
    if payload.bloc_id and payload.bloc_id != row.bloc_id:
        bloc = IntelBloc.objects.filter(pk=payload.bloc_id).first()
        if bloc is None:
            return 400, ErrorResponse(detail="No such bloc.")
        if IntelAffiliation.objects.filter(
            entity=row.entity, bloc=bloc
        ).exists():
            return 400, ErrorResponse(
                detail=f"{row.entity.name} already has a row in {bloc.name}."
            )
        row.bloc = bloc
    if payload.relation:
        row.relation = payload.relation
    row.status = payload.status
    row.note = " ".join(payload.note.split())[:200]
    row.decided_by = request.user
    row.decided_at = timezone.now()
    row.save()
    if row.status == IntelAffiliation.Status.CONFIRMED:
        # One confirmed home: other suggestions for the same subject go.
        IntelAffiliation.objects.filter(
            entity=row.entity, status=IntelAffiliation.Status.SUGGESTED
        ).exclude(pk=row.pk).delete()
    resolve.invalidate()
    return affiliation_out(row)
