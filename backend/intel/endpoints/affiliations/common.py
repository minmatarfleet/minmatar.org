"""Shared by the affiliation endpoints: the gate, names and serializers."""

from __future__ import annotations

from groups.helpers.feature_access import can_use_feature
from intel.affiliations import resolve
from intel.models import IntelAffiliation, IntelBloc, IntelEntity

MANAGE_FEATURE = "intel.affiliations"
FORBIDDEN = "You can't manage intel affiliations."


def endpoint(method: str, path: str, **spec):
    """Mark a handler with its route; the package router registers it.

    One router per path prefix, so a GET and a PATCH on the same path (in
    their own modules) end up as one URL with two methods.
    """

    def mark(handler):
        handler.route = (method, path, spec)
        return handler

    return mark


def can_manage(user) -> bool:
    return can_use_feature(user, MANAGE_FEATURE)


def entity_ref(entity: IntelEntity) -> dict:
    return {
        "kind": entity.kind,
        "id": entity.eve_id,
        "name": entity.name or f"{entity.get_kind_display()} {entity.eve_id}",
    }


def bloc_ref(bloc: IntelBloc, *, likely: bool = False) -> dict:
    return {"id": bloc.id, "name": bloc.name, "likely": likely}


def group_bloc_ref(kind: str, eve_id: int, blocs: dict) -> dict | None:
    return resolve.public_entry(
        resolve.bloc_for_group(kind, eve_id, blocs=blocs)
    )


def affiliation_out(row: IntelAffiliation) -> dict:
    decided_by = None
    if row.decided_by_id:
        decided_by = row.decided_by.username
    return {
        "id": row.id,
        "entity": entity_ref(row.entity),
        "bloc": bloc_ref(row.bloc),
        "relation": row.relation,
        "status": row.status,
        "source": row.source,
        "confidence": row.confidence,
        "evidence": row.evidence or {},
        "first_month": row.first_month,
        "last_month": row.last_month,
        "ended": row.ended,
        "decided_by": decided_by,
        "decided_at": row.decided_at,
        "note": row.note,
    }


def affiliations_query():
    return IntelAffiliation.objects.select_related(
        "entity", "bloc", "decided_by"
    )


def bloc_summary(bloc: IntelBloc) -> dict:
    live = [
        row
        for row in bloc.affiliations.all()
        if row.status != IntelAffiliation.Status.REJECTED and not row.ended
    ]
    return {
        "id": bloc.id,
        "name": bloc.name,
        "anchor": entity_ref(bloc.anchor) if bloc.anchor_id else None,
        "notes": bloc.notes,
        "manual": bloc.manual,
        "groups": sum(
            row.entity.kind != IntelEntity.Kind.CHARACTER for row in live
        ),
        "associates": sum(
            row.entity.kind == IntelEntity.Kind.CHARACTER for row in live
        ),
        "suggested": sum(
            row.status == IntelAffiliation.Status.SUGGESTED for row in live
        ),
    }
