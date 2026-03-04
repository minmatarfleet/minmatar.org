"""DELETE "/{tribe_id}/groups/{group_id}/memberships/{membership_id}" - leave or remove."""

from django.utils import timezone
from ninja import Router

from authentication import AuthBearer
from tribes.helpers import user_can_manage_group
from tribes.models import (
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacterHistory,
)

PATH = "/{tribe_id}/groups/{group_id}/memberships/{membership_id}"
METHOD = "delete"
ROUTE_SPEC = {
    "summary": "Leave (own) or remove (chief) a tribe group membership.",
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
    is_forced_removal = is_manager and not is_own

    if is_forced_removal:
        inactive_reason = "removed"
        leave_reason = (
            TribeGroupMembershipCharacterHistory.LEAVE_REASON_REMOVED
        )
        membership.removed_by = request.user
    else:
        inactive_reason = "left"
        leave_reason = (
            TribeGroupMembershipCharacterHistory.LEAVE_REASON_VOLUNTARY
        )

    # Write history row for each currently committed character before clearing them.
    current_chars = list(
        membership.characters.select_related("character").all()
    )
    char_history = [
        TribeGroupMembershipCharacterHistory(
            membership=membership,
            character=mc.character,
            action=TribeGroupMembershipCharacterHistory.ACTION_REMOVED,
            at=now,
            by=request.user,
            leave_reason=leave_reason,
        )
        for mc in current_chars
    ]
    TribeGroupMembershipCharacterHistory.objects.bulk_create(char_history)

    # Remove all current character links.
    membership.characters.all().delete()

    membership.status = TribeGroupMembership.STATUS_INACTIVE
    membership.left_at = now
    membership.history_inactive_reason = inactive_reason
    membership.history_changed_by = request.user
    membership.save()

    return 200, {"detail": "Membership ended."}


router.delete(PATH, **ROUTE_SPEC)(delete_membership)
