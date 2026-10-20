"""POST /blocs/{bloc_id}/merge - fold one bloc into another."""

from __future__ import annotations

from django.db import transaction

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
    BlocMergeRequest,
    BlocSummarySchema,
)
from intel.models import IntelAffiliation, IntelBloc


@endpoint(
    "post",
    "/{int:bloc_id}/merge",
    summary="Merge a bloc into another",
    description=(
        "The merged bloc's anchor becomes a confirmed alt alliance of the "
        "other, and its affiliations move across (where the other bloc "
        "already has a row for the same subject, that row is kept)."
    ),
    auth=AuthBearer(),
    response={
        200: BlocSummarySchema,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def post_bloc_merge(request, bloc_id: int, payload: BlocMergeRequest):
    if not can_manage(request.user):
        return 403, ErrorResponse(detail=FORBIDDEN)
    if bloc_id == payload.into_bloc_id:
        return 400, ErrorResponse(detail="Pick a different bloc.")
    source = IntelBloc.objects.filter(pk=bloc_id).first()
    target = IntelBloc.objects.filter(pk=payload.into_bloc_id).first()
    if source is None or target is None:
        return 404, ErrorResponse(detail="No such bloc.")
    with transaction.atomic():
        taken = set(
            IntelAffiliation.objects.filter(bloc=target).values_list(
                "entity_id", flat=True
            )
        )
        if target.anchor_id:
            taken.add(target.anchor_id)
        IntelAffiliation.objects.filter(bloc=source).exclude(
            entity_id__in=taken
        ).update(bloc=target)
        if source.anchor_id and source.anchor_id not in taken:
            IntelAffiliation.objects.create(
                entity_id=source.anchor_id,
                bloc=target,
                relation=IntelAffiliation.Relation.ALT,
                status=IntelAffiliation.Status.CONFIRMED,
                source=IntelAffiliation.Source.MANUAL,
                confidence=1.0,
                decided_by=request.user,
                note=f"Merged from {source.name}",
            )
        if source.notes and source.notes not in target.notes:
            target.notes = "\n\n".join(
                filter(None, [target.notes, source.notes])
            )
        target.manual = True
        target.save()
        source.delete()
    resolve.invalidate()
    return bloc_summary(blocs_with_rows().get(pk=target.pk))
