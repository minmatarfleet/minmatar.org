"""GET /entities/{kind}/{eve_id} - one group or pilot and the evidence."""

from __future__ import annotations

from collections import defaultdict

from django.db.models import Sum

from app.errors import ErrorResponse
from authentication import AuthBearer
from intel.affiliations import resolve
from intel.affiliations.names import names_for
from intel.affiliations.score import partners, window
from intel.endpoints.affiliations.common import (
    FORBIDDEN,
    affiliation_out,
    affiliations_query,
    can_manage,
    endpoint,
    group_bloc_ref,
)
from intel.endpoints.affiliations.schemas import EntityProfileResponse
from intel.models import IntelCoAttack, IntelEntity, IntelSampleMonth

MAX_ROWS = 25
KINDS = {choice.value for choice in IntelEntity.Kind}


def _partner_rows(found, kills: int, blocs: dict) -> list[dict]:
    top = sorted(found, key=lambda p: -p["shared"])[:MAX_ROWS]
    names = names_for(row["id"] for row in top)
    return [
        {
            **row,
            "name": names.get(row["id"], f"{row['kind']} {row['id']}"),
            "share": round(row["shared"] / kills, 3) if kills else None,
            "bloc": group_bloc_ref(row["kind"], row["id"], blocs),
        }
        for row in top
    ]


def _group_partners(entity, months) -> list[dict]:
    return [
        {
            "kind": p.kind,
            "id": p.eve_id,
            "shared": p.shared,
            "months_together": len(p.months),
            "against": p.against,
            "militia_shared": p.militia_shared,
            "last_month": p.last_month,
        }
        for p in partners(entity, months).values()
        if p.shared
    ]


def _characters(entity, months) -> list[dict]:
    rows = IntelCoAttack.objects.filter(
        entity=entity, month__in=months, partner_kind="character"
    ).values_list("partner_id", "month", "shared", "militia_shared")
    found: dict[int, dict] = defaultdict(
        lambda: {"shared": 0, "militia_shared": 0, "months": set()}
    )
    for partner_id, month, shared, militia in rows:
        found[partner_id]["shared"] += shared
        found[partner_id]["militia_shared"] += militia
        found[partner_id]["months"].add(month)
    return [
        {
            "kind": "character",
            "id": partner_id,
            "shared": row["shared"],
            "months_together": len(row["months"]),
            "against": 0,
            "militia_shared": row["militia_shared"],
            "last_month": max(row["months"]),
        }
        for partner_id, row in found.items()
    ]


def _flies_with(kind: str, eve_id: int, months) -> list[dict]:
    """The investigated groups whose kills this pilot or group is on."""
    rows = IntelCoAttack.objects.filter(
        partner_kind=kind, partner_id=eve_id, month__in=months
    ).values_list(
        "entity__kind", "entity__eve_id", "month", "shared", "militia_shared"
    )
    found: dict[tuple, dict] = defaultdict(
        lambda: {"shared": 0, "militia_shared": 0, "months": set()}
    )
    for group_kind, group_id, month, shared, militia in rows:
        if not shared:
            continue
        found[(group_kind, group_id)]["shared"] += shared
        found[(group_kind, group_id)]["militia_shared"] += militia
        found[(group_kind, group_id)]["months"].add(month)
    return [
        {
            "kind": group_kind,
            "id": group_id,
            "shared": row["shared"],
            "months_together": len(row["months"]),
            "against": 0,
            "militia_shared": row["militia_shared"],
            "last_month": max(row["months"]),
        }
        for (group_kind, group_id), row in found.items()
    ]


@endpoint(
    "get",
    "/{kind}/{int:eve_id}",
    summary="A group or pilot in the affiliation database, with evidence",
    auth=AuthBearer(),
    response={
        200: EntityProfileResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def get_entity(request, kind: str, eve_id: int):
    if not can_manage(request.user):
        return 403, ErrorResponse(detail=FORBIDDEN)
    if kind not in KINDS:
        return 404, ErrorResponse(detail="No such kind.")
    months = window()
    entity = IntelEntity.objects.filter(kind=kind, eve_id=eve_id).first()
    blocs = resolve.bloc_map()
    totals = {"kills": 0, "losses": 0, "months": 0}
    if entity is not None:
        sampled = IntelSampleMonth.objects.filter(
            entity=entity, month__in=months
        )
        totals = {
            "kills": sampled.aggregate(n=Sum("kills"))["n"] or 0,
            "losses": sampled.aggregate(n=Sum("losses"))["n"] or 0,
            "months": sampled.count(),
        }
    if kind == IntelEntity.Kind.CHARACTER or entity is None:
        partner_rows = _flies_with(kind, eve_id, months)
        character_rows = []
        # Shares are of the group's kills, so there is no one denominator.
        share_of = 0
    else:
        partner_rows = _group_partners(entity, months)
        character_rows = _characters(entity, months)
        share_of = totals["kills"]
    if entity is None and not partner_rows:
        return 404, ErrorResponse(detail="Not in the affiliation database.")
    name = (entity.name if entity else "") or names_for([eve_id]).get(
        eve_id, f"{kind} {eve_id}"
    )
    rows = (
        affiliations_query().filter(entity=entity).order_by("status")
        if entity
        else []
    )
    return EntityProfileResponse(
        kind=kind,
        id=eve_id,
        name=name,
        status=entity.status if entity else IntelEntity.Status.NEW,
        sightings=entity.sightings if entity else 0,
        first_seen_at=entity.first_seen_at if entity else None,
        last_seen_at=entity.last_seen_at if entity else None,
        investigated_at=entity.investigated_at if entity else None,
        faction_id=entity.faction_id if entity else None,
        kills_sampled=totals["kills"],
        losses_sampled=totals["losses"],
        months_sampled=totals["months"],
        bloc=resolve.public_entry(
            resolve.bloc_for_group(kind, eve_id, blocs=blocs)
        ),
        alliance_history=(entity.alliance_history or []) if entity else [],
        partners=_partner_rows(partner_rows, share_of, blocs),
        characters=_partner_rows(character_rows, share_of, blocs),
        affiliations=[affiliation_out(row) for row in rows],
    )
