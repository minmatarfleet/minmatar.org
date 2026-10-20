"""PATCH /blocs/{bloc_id} - rename a bloc or edit its notes."""

from __future__ import annotations

from app.errors import ErrorResponse
from authentication import AuthBearer
from intel.affiliations import resolve
from intel.endpoints.affiliations.common import (
    FORBIDDEN,
    bloc_summary,
    can_manage,
    endpoint,
)
from intel.endpoints.affiliations.get_blocs import blocs_with_rows
from intel.endpoints.affiliations.schemas import (
    BlocPatchRequest,
    BlocSummarySchema,
)


@endpoint(
    "patch",
    "/{int:bloc_id}",
    summary="Rename a bloc or edit its notes",
    auth=AuthBearer(),
    response={
        200: BlocSummarySchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def patch_bloc(request, bloc_id: int, payload: BlocPatchRequest):
    if not can_manage(request.user):
        return 403, ErrorResponse(detail=FORBIDDEN)
    bloc = blocs_with_rows().filter(pk=bloc_id).first()
    if bloc is None:
        return 404, ErrorResponse(detail="No such bloc.")
    if payload.name is not None:
        name = " ".join(payload.name.split())[:128]
        if not name:
            return 400, ErrorResponse(detail="A bloc needs a name.")
        bloc.name = name
    if payload.notes is not None:
        bloc.notes = payload.notes.strip()[:4000]
    # A bloc someone has named or annotated is kept even when empty.
    bloc.manual = True
    bloc.save()
    resolve.invalidate()
    return bloc_summary(bloc)
