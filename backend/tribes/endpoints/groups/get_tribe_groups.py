"""GET "/{tribe_id}/groups" - list active groups in a tribe."""

from typing import List

from django.db.models import Count, Q
from ninja import Router

from authentication import AuthOptional
from tribes.endpoints.groups.schemas import TribeGroupSchema
from tribes.endpoints.groups.serializers import serialize_tribe_group
from tribes.helpers.publishing import active_member_group_ids
from tribes.models import Tribe, TribeGroupMembership

PATH = "/{tribe_id}/groups"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List active groups in a tribe.",
    "response": {200: List[TribeGroupSchema], 404: dict},
    "auth": AuthOptional(),
}

router = Router(tags=["Tribes - Groups"])


def get_tribe_groups(request, tribe_id: int):
    tribe = Tribe.objects.filter(pk=tribe_id).first()
    if not tribe:
        return 404, {"detail": "Tribe not found."}

    groups = (
        tribe.groups.filter(is_active=True)
        .select_related(
            "chief__eveplayer__primary_character",
            "tribe",
            "group__discord_group",
        )
        .prefetch_related(
            "allowed_affiliations",
            "ranks",
            "requirements__asset_types__eve_type",
            "requirements__asset_types__locations",
            "requirements__qualifying_skills__eve_type",
        )
        .annotate(
            active_member_count=Count(
                "memberships",
                filter=Q(
                    memberships__status=TribeGroupMembership.STATUS_ACTIVE
                ),
            )
        )
    )
    member_group_ids = active_member_group_ids(request.user)
    result = [
        serialize_tribe_group(
            tg,
            request_user=request.user,
            member_count=tg.active_member_count,
            member_group_ids=member_group_ids,
        )
        for tg in groups
    ]
    return 200, result


router.get(PATH, **ROUTE_SPEC)(get_tribe_groups)
