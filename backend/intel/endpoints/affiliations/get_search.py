"""GET /entities/search?q= - find a group or pilot by name."""

from __future__ import annotations

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.client import EsiClient
from intel.affiliations import resolve
from intel.endpoints.affiliations.common import (
    FORBIDDEN,
    can_manage,
    endpoint,
    entity_ref,
    group_bloc_ref,
)
from intel.endpoints.affiliations.schemas import EntitySearchListResponse
from intel.models import IntelEntity

MAX_RESULTS = 20
ESI_KINDS = {
    "alliances": "alliance",
    "corporations": "corporation",
    "characters": "character",
}


def _esi_exact(query: str) -> list[dict]:
    """An exact-name match ESI knows that we don't have yet."""
    response = EsiClient(None).resolve_universe_ids([query])
    if not response.success():
        return []
    found = []
    for key, kind in ESI_KINDS.items():
        for row in (response.results() or {}).get(key) or []:
            found.append(
                {"kind": kind, "id": int(row["id"]), "name": row["name"]}
            )
    return found


@endpoint(
    "get",
    "/search",
    summary="Find a group or pilot by name",
    auth=AuthBearer(),
    response={200: EntitySearchListResponse, 403: ErrorResponse},
)
def get_entity_search(request, q: str = ""):
    if not can_manage(request.user):
        return 403, ErrorResponse(detail=FORBIDDEN)
    query = " ".join(q.split())
    if len(query) < 3:
        return EntitySearchListResponse(results=[])
    blocs = resolve.bloc_map()
    rows = IntelEntity.objects.filter(name__icontains=query).order_by(
        "-sightings"
    )[:MAX_RESULTS]
    results = [
        {
            **entity_ref(row),
            "status": row.status,
            "bloc": group_bloc_ref(row.kind, row.eve_id, blocs),
        }
        for row in rows
    ]
    if not any(r["name"].lower() == query.lower() for r in results):
        known = {(r["kind"], r["id"]) for r in results}
        for row in _esi_exact(query):
            if (row["kind"], row["id"]) not in known:
                results.insert(
                    0,
                    {
                        **row,
                        "status": IntelEntity.Status.NEW,
                        "bloc": group_bloc_ref(row["kind"], row["id"], blocs),
                    },
                )
    return EntitySearchListResponse(results=results[:MAX_RESULTS])
