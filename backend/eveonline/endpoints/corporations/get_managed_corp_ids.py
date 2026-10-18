"""GET /managed - get IDs of corporations the current user can manage."""

from typing import List

from ninja import Router

from authentication import AuthBearer
from eveonline.helpers.alliances import member_corporations
from eveonline.helpers.characters.identity import owned_by_q
from eveonline.helpers.corporations.permissions import can_manage_corporation
from eveonline.models import EveCorporation

router = Router(tags=["Corporations"])


@router.get(
    "managed",
    response=List[int],
    auth=AuthBearer(),
    summary="Get IDs of corporations the current user can manage",
)
def get_managed_corp_ids(request) -> List[int]:
    user = request.user
    corporations = (
        member_corporations()
        .select_related("ceo", "ceo__token")
        .prefetch_related("directors__token")
    )
    ids = {
        corp.corporation_id
        for corp in corporations
        if can_manage_corporation(user, corp)
    }
    ids.update(
        EveCorporation.objects.filter(
            owned_by_q(user.id, "directors__")
        ).values_list("corporation_id", flat=True)
    )
    ids.update(
        EveCorporation.objects.filter(
            owned_by_q(user.id, "ceo__")
        ).values_list("corporation_id", flat=True)
    )
    return sorted(ids)
