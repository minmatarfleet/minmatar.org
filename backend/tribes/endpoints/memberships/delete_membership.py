"""DELETE "/{tribe_id}/groups/{group_id}/memberships/{membership_id}" - leave or remove."""

from django.utils import timezone
from ninja import Router

from authentication import AuthBearer
from tribes.helpers import user_can_manage_group
from tribes.models import TribeGroup, TribeGroupMembership

PATH = "/{tribe_id}/groups/{group_id}/memberships/{membership_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "summary": "Leave (own) or remove (chief/elder) a tribe group membership.",
    "response": {200: dict, 403: dict, 404: dict},
    "auth": AuthBearer(),
}

router = Router(tags=["Tribes - Memberships"])


def delete_membership(
    request, tribe_id: int, group_id: int, membership_id: int
):
    tg = TribeGroup.objects.filter(pk=group_id, tribe_id=tribe_id).first()
    if not tg:
        return 404, {"detail": "TribeGroup not found."}

    membership = TribeGroupMembership.objects.filter(
        pk=membership_id, tribe_group=tg
    ).first()
    if not membership:
        return 404, {"detail": "Membership not found."}

    is_own = membership.user_id == request.user.pk
    is_manager = user_can_manage_group(request.user, tg)

    if not is_own and not is_manager:
        return 403, {"detail": "You cannot remove this membership."}

    now = timezone.now()
    if is_own and not is_manager:
        membership.status = TribeGroupMembership.STATUS_LEFT
        membership.left_at = now
    else:
        membership.status = TribeGroupMembership.STATUS_REMOVED
        membership.removed_by = request.user
        membership.left_at = now
    membership.save()

    membership.characters.filter(left_at__isnull=True).update(
        left_at=now,
        leave_reason="removed" if is_manager and not is_own else "voluntary",
    )

    return 200, {"detail": "Membership ended."}


router.delete(PATH, **ROUTE_SPEC)(delete_membership)
