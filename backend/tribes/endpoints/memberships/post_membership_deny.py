"""POST "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/deny"."""

from ninja import Router

from authentication import AuthBearer
from tribes.endpoints.memberships.schemas import MembershipSchema
from tribes.endpoints.memberships.serializers import serialize_membership
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup, TribeGroupMembership

PATH = "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/deny"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Deny a pending membership (chief only).",
    "response": {200: MembershipSchema, 400: dict, 403: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Memberships"])


def post_membership_deny(
    request, tribe_id: int, group_id: int, membership_id: int
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}
    if not user_can_manage_group(request.user, tg):
        return 403, {
            "detail": "You do not have permission to deny memberships here."
        }

    membership = TribeGroupMembership.objects.filter(
        pk=membership_id, tribe_group=tg
    ).first()
    if not membership:
        return 404, {"detail": "Membership not found."}
    if membership.status != TribeGroupMembership.STATUS_PENDING:
        return 400, {
            "detail": f"Cannot deny a membership with status '{membership.status}'."
        }

    membership.status = TribeGroupMembership.STATUS_INACTIVE
    membership.history_inactive_reason = "denied"
    membership.history_changed_by = request.user
    membership.save()

    membership = (
        TribeGroupMembership.objects.select_related(
            "user__eveplayer__primary_character",
        )
        .prefetch_related("characters__character")
        .get(pk=membership.pk)
    )
    return 200, serialize_membership(
        membership,
        include_requirement_status=True,
        include_characters=True,
    )


router.post(PATH, **ROUTE_SPEC)(post_membership_deny)
