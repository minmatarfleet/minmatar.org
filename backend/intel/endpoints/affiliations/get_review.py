"""GET /affiliations/review - suggested affiliations and the queue."""

from __future__ import annotations

from django.db.models import Count, F

from app.errors import ErrorResponse
from authentication import AuthBearer
from intel.endpoints.affiliations.common import (
    FORBIDDEN,
    affiliation_out,
    affiliations_query,
    can_manage,
    endpoint,
    entity_ref,
)
from intel.endpoints.affiliations.schemas import ReviewResponse
from intel.models import IntelAffiliation, IntelEntity

MAX_SUGGESTIONS = 200
QUEUE_SHOWN = 10


def queue_stats() -> dict:
    counts = dict(
        IntelEntity.objects.exclude(kind=IntelEntity.Kind.CHARACTER)
        .values_list("status")
        .annotate(total=Count("id"))
        .values_list("status", "total")
    )
    upcoming = IntelEntity.objects.filter(
        status=IntelEntity.Status.QUEUED
    ).order_by(
        "-priority", F("queued_at").asc(nulls_first=True), "-sightings"
    )[
        :QUEUE_SHOWN
    ]
    return {
        "queued": counts.get(IntelEntity.Status.QUEUED, 0),
        "investigating": counts.get(IntelEntity.Status.INVESTIGATING, 0),
        "investigated": counts.get(IntelEntity.Status.DONE, 0),
        "failed": counts.get(IntelEntity.Status.FAILED, 0),
        "next": [
            {
                **entity_ref(entity),
                "sightings": entity.sightings,
                "priority": entity.priority,
            }
            for entity in upcoming
        ],
    }


@endpoint(
    "get",
    "/review",
    summary="Suggested affiliations waiting for the intel team",
    auth=AuthBearer(),
    response={200: ReviewResponse, 403: ErrorResponse},
)
def get_affiliation_review(request):
    if not can_manage(request.user):
        return 403, ErrorResponse(detail=FORBIDDEN)
    rows = affiliations_query().filter(
        status=IntelAffiliation.Status.SUGGESTED, ended=False
    )
    # Groups first (they move whole rosters), then the strongest.
    rows = sorted(
        rows.order_by("-confidence")[:MAX_SUGGESTIONS],
        key=lambda row: (
            row.entity.kind == IntelEntity.Kind.CHARACTER,
            -row.confidence,
        ),
    )
    return ReviewResponse(
        suggestions=[affiliation_out(row) for row in rows],
        queue=queue_stats(),
    )
