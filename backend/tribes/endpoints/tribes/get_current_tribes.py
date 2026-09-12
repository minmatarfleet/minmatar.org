"""GET "/current" - tribes the current user is a member of."""

from typing import List

from ninja import Router

from authentication import AuthBearer
from tribes.endpoints.tribes.schemas import TribeSchema
from tribes.endpoints.tribes.serializers import serialize_tribe
from tribes.models import Tribe, TribeGroupMembership

PATH = "/current"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "Tribes the current user is a member of (via any TribeGroup).",
    "response": {200: List[TribeSchema]},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes"])


def get_current_tribes(request):
    tribe_ids = (
        TribeGroupMembership.objects.filter(
            user=request.user, status=TribeGroupMembership.STATUS_ACTIVE
        )
        .values_list("tribe_group__tribe_id", flat=True)
        .distinct()
    )
    return [
        serialize_tribe(tribe)
        for tribe in Tribe.objects.filter(
            pk__in=tribe_ids, is_active=True
        ).select_related(
            "chief__eveplayer__primary_character",
        )
    ]


router.get(PATH, **ROUTE_SPEC)(get_current_tribes)
