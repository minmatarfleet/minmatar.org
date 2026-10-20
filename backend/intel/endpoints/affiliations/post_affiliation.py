"""POST /affiliations - add an affiliation by hand."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.client import EsiClient
from intel.affiliations import resolve
from intel.affiliations.names import names_for
from intel.endpoints.affiliations.common import (
    FORBIDDEN,
    affiliation_out,
    can_manage,
    endpoint,
)
from intel.endpoints.affiliations.schemas import (
    AffiliationSchema,
    ManualAffiliationRequest,
)
from intel.models import IntelAffiliation, IntelBloc, IntelEntity

ESI_ID_KEYS = {
    "alliance": "alliances",
    "corporation": "corporations",
    "character": "characters",
}


def _resolve_id(kind: str, name: str) -> int | None:
    response = EsiClient(None).resolve_universe_ids([name.strip()])
    if not response.success():
        return None
    for row in (response.results() or {}).get(ESI_ID_KEYS[kind]) or []:
        if row.get("name", "").lower() == name.strip().lower():
            return int(row["id"])
    return None


@endpoint(
    "post",
    "",
    summary="Add an affiliation by hand",
    description=(
        "Name the subject by EVE id or exact name, and the bloc by id or a "
        "new name. Hand-made affiliations are confirmed."
    ),
    auth=AuthBearer(),
    response={200: AffiliationSchema, 400: ErrorResponse, 403: ErrorResponse},
)
def post_affiliation(request, payload: ManualAffiliationRequest):
    if not can_manage(request.user):
        return 403, ErrorResponse(detail=FORBIDDEN)
    eve_id = payload.eve_id
    if not eve_id and payload.name:
        eve_id = _resolve_id(payload.kind, payload.name)
    if not eve_id:
        return 400, ErrorResponse(detail=f"No {payload.kind} by that name.")
    new_name = " ".join((payload.new_bloc_name or "").split())[:128]
    if not payload.bloc_id and not new_name:
        return 400, ErrorResponse(detail="Pick a bloc or name a new one.")
    with transaction.atomic():
        entity, _ = IntelEntity.objects.get_or_create(
            kind=payload.kind, eve_id=eve_id
        )
        if not entity.name:
            entity.name = names_for([eve_id]).get(eve_id, "")
            entity.save(update_fields=["name", "updated_at"])
        if payload.bloc_id:
            bloc = IntelBloc.objects.filter(pk=payload.bloc_id).first()
            if bloc is None:
                return 400, ErrorResponse(detail="No such bloc.")
        else:
            bloc = IntelBloc.objects.create(name=new_name, manual=True)
        if bloc.anchor_id == entity.pk:
            return 400, ErrorResponse(
                detail=f"{entity.name} is the group {bloc.name} is named after."
            )
        row, _ = IntelAffiliation.objects.update_or_create(
            entity=entity,
            bloc=bloc,
            defaults={
                "relation": payload.relation,
                "status": IntelAffiliation.Status.CONFIRMED,
                "source": IntelAffiliation.Source.MANUAL,
                "confidence": 1.0,
                "ended": False,
                "note": " ".join(payload.note.split())[:200],
                "decided_by": request.user,
                "decided_at": timezone.now(),
            },
        )
        IntelAffiliation.objects.filter(
            entity=entity, status=IntelAffiliation.Status.SUGGESTED
        ).exclude(pk=row.pk).delete()
    resolve.invalidate()
    return affiliation_out(row)
