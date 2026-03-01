"""GET "/{tribe_id}/groups/{group_id}/candidates" - skillset-based recruitment candidates."""

from typing import List, Optional

from ninja import Router

from authentication import AuthBearer
from tribes.endpoints.outreach.schemas import CandidateSchema
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup

PATH = "/{tribe_id}/groups/{group_id}/candidates"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Alliance characters close to or fully meeting skillset requirements (chiefs/elders).",
    "response": {200: List[CandidateSchema], 403: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Outreach"])


def get_candidates(
    request,
    tribe_id: int,
    group_id: int,
    minimum_progress: Optional[float] = 0.75,
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, tg):
        return 403, {"detail": "Chiefs and elders only."}

    # Skillset-based requirements have been removed; candidates are no longer
    # driven by a skillset type. Return an empty list for now.
    return 200, []


router.get(PATH, **ROUTE_SPEC)(get_candidates)
