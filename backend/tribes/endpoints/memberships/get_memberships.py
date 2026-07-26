"""GET "/{tribe_id}/groups/{group_id}/memberships" - list memberships."""

from typing import List, Optional

from authentication import AuthBearer
from tribes.endpoints.memberships.schemas import MembershipSchema
from tribes.endpoints.memberships.serializers import serialize_membership
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup, TribeGroupMembership

PATH = "/{tribe_id}/groups/{group_id}/memberships"
METHOD = "get"
ROUTE_SPEC = {
    "summary": "List memberships for a tribe group (chief sees all; members see own).",
    "description": (
        "Use mine=true on tribe landing tiles to fetch only the caller's "
        "membership without live requirement checks. Use include_requirements=true "
        "on the members management page when chiefs need per-character qualify status."
    ),
    "response": {200: List[MembershipSchema], 403: dict, 404: dict},
    "auth": AuthBearer(),
}


def get_memberships(
    request,
    tribe_id: int,
    group_id: int,
    status: Optional[str] = None,
    mine: bool = False,
    include_requirements: bool = False,
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}

    can_manage = user_can_manage_group(request.user, tg)

    if mine or not can_manage:
        qs = TribeGroupMembership.objects.filter(
            tribe_group=tg, user=request.user
        )
    else:
        qs = TribeGroupMembership.objects.filter(tribe_group=tg)

    if status:
        qs = qs.filter(status=status)

    # Landing / own-membership views need committed characters but not live
    # asset/skill evaluation. Requirement checks are expensive (N+1 against
    # EveCharacterAsset) and only belong on the members management page.
    include_characters = mine or can_manage
    check_requirements = include_requirements and can_manage and not mine

    qs = qs.select_related(
        "tribe_group__tribe",
        "user__eveplayer__primary_character",
        "rank",
    ).prefetch_related(
        "characters__character",
        "tribe_group__requirements__asset_types__eve_type",
        "tribe_group__requirements__qualifying_skills__eve_type",
    )

    return 200, [
        serialize_membership(
            m,
            include_requirement_status=check_requirements,
            include_characters=include_characters,
        )
        for m in qs
    ]
