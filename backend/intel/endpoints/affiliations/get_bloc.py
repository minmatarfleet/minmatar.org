"""GET /blocs/{bloc_id} - one bloc and every affiliation it has had."""

from __future__ import annotations

from app.errors import ErrorResponse
from authentication import AuthBearer
from intel.endpoints.affiliations.common import (
    FORBIDDEN,
    affiliation_out,
    bloc_summary,
    can_manage,
    endpoint,
)
from intel.endpoints.affiliations.get_blocs import blocs_with_rows
from intel.endpoints.affiliations.schemas import BlocDetailResponse
from intel.models import IntelAffiliation

STATUS_ORDER = {
    IntelAffiliation.Status.CONFIRMED: 0,
    IntelAffiliation.Status.SUGGESTED: 1,
    IntelAffiliation.Status.REJECTED: 2,
}


@endpoint(
    "get",
    "/{int:bloc_id}",
    summary="One bloc: its groups, associates, and rejected suggestions",
    auth=AuthBearer(),
    response={200: BlocDetailResponse, 403: ErrorResponse, 404: ErrorResponse},
)
def get_bloc(request, bloc_id: int):
    if not can_manage(request.user):
        return 403, ErrorResponse(detail=FORBIDDEN)
    bloc = blocs_with_rows().filter(pk=bloc_id).first()
    if bloc is None:
        return 404, ErrorResponse(detail="No such bloc.")
    rows = sorted(
        bloc.affiliations.all(),
        key=lambda row: (
            row.ended,
            STATUS_ORDER[row.status],
            row.entity.kind == "character",
            -row.confidence,
        ),
    )
    return BlocDetailResponse(
        **bloc_summary(bloc),
        affiliations=[affiliation_out(row) for row in rows],
    )
