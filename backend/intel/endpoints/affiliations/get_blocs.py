"""GET /blocs - every bloc with how many groups and associates it has."""

from __future__ import annotations

from django.db.models import Prefetch

from app.errors import ErrorResponse
from authentication import AuthBearer
from intel.endpoints.affiliations.common import (
    FORBIDDEN,
    affiliations_query,
    bloc_summary,
    can_manage,
    endpoint,
)
from intel.endpoints.affiliations.schemas import BlocListResponse
from intel.models import IntelBloc


def blocs_with_rows():
    return IntelBloc.objects.select_related("anchor").prefetch_related(
        Prefetch("affiliations", queryset=affiliations_query())
    )


@endpoint(
    "get",
    "",
    summary="Every bloc in the affiliation database",
    auth=AuthBearer(),
    response={200: BlocListResponse, 403: ErrorResponse},
)
def get_blocs(request):
    if not can_manage(request.user):
        return 403, ErrorResponse(detail=FORBIDDEN)
    blocs = [bloc_summary(bloc) for bloc in blocs_with_rows()]
    blocs = [
        bloc
        for bloc in blocs
        if bloc["manual"] or bloc["groups"] or bloc["associates"]
    ]
    blocs.sort(key=lambda b: (-(b["groups"] + b["associates"]), b["name"]))
    return BlocListResponse(blocs=blocs)
