"""PATCH "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/rank"."""

from ninja import Router

from authentication import AuthBearer
from tribes.endpoints.memberships.schemas import (
    MembershipSchema,
    SetMembershipRankRequest,
)
from tribes.endpoints.memberships.serializers import serialize_membership
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup, TribeGroupMembership, TribeGroupRank

PATH = "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/rank"
METHOD = "patch"
ROUTE_SPEC = {
    "summary": "Set or clear a membership rank (chief only).",
    "response": {200: MembershipSchema, 400: dict, 403: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Memberships"])


def patch_membership_rank(
    request,
    tribe_id: int,
    group_id: int,
    membership_id: int,
    payload: SetMembershipRankRequest,
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, tg):
        return 403, {
            "detail": "You do not have permission to manage memberships here."
        }

    membership = (
        TribeGroupMembership.objects.filter(pk=membership_id, tribe_group=tg)
        .select_related(
            "tribe_group__tribe",
            "user__eveplayer__primary_character",
            "rank",
        )
        .first()
    )
    if not membership:
        return 404, {"detail": "Membership not found."}

    if payload.rank_id is None:
        membership.rank = None
    else:
        rank = TribeGroupRank.objects.filter(
            pk=payload.rank_id, tribe_group=tg
        ).first()
        if not rank:
            return 400, {"detail": "Rank does not exist for this tribe group."}
        membership.rank = rank

    membership.history_changed_by = request.user
    membership.save()

    membership = (
        TribeGroupMembership.objects.select_related(
            "tribe_group__tribe",
            "user__eveplayer__primary_character",
            "rank",
        )
        .prefetch_related("characters__character")
        .get(pk=membership.pk)
    )
    return 200, serialize_membership(
        membership,
        include_requirement_status=True,
        include_characters=True,
    )


router.patch(PATH, **ROUTE_SPEC)(patch_membership_rank)
