"""POST "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/deny"."""

from ninja import Router

from authentication import AuthBearer
from tribes.endpoints.memberships.schemas import MembershipSchema
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup, TribeGroupMembership

PATH = "/{tribe_id}/groups/{group_id}/memberships/{membership_id}/deny"
METHOD = "post"
ROUTE_SPEC = {
    "summary": "Deny a pending membership (chiefs/elders only).",
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

    membership.status = TribeGroupMembership.STATUS_DENIED
    membership.save()

    return 200, MembershipSchema(
        id=membership.pk,
        user_id=membership.user_id,
        tribe_group_id=membership.tribe_group_id,
        tribe_group_name=str(membership.tribe_group),
        tribe_id=membership.tribe_group.tribe_id,
        status=membership.status,
        requirement_snapshot=membership.requirement_snapshot,
        created_at=membership.created_at.isoformat(),
        approved_by_id=membership.approved_by_id,
        approved_at=(
            membership.approved_at.isoformat()
            if membership.approved_at
            else None
        ),
        left_at=membership.left_at.isoformat() if membership.left_at else None,
        characters=[],
    )


router.post(PATH, **ROUTE_SPEC)(post_membership_deny)
