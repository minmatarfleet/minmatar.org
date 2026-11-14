"""Promote, put on leave, or take off leave: one path for every screen.

The alliance health lists and the corp Members tab both change a member's
community status through here, so they share the same permission checks
(``can_put_on_leave`` for leave, ``can_mutate_status`` otherwise), the same
allowed transitions and the same snapshot patch.
"""

from dataclasses import dataclass

from django.contrib.auth.models import User

from alliance.helpers.access import can_mutate_status, can_put_on_leave
from alliance.helpers.health_snapshot_patch import (
    apply_status_change_to_latest_snapshot,
)
from groups.helpers import process_bulk_community_status_row
from groups.models import UserCommunityStatus

ACTIONS = {
    "promote": UserCommunityStatus.STATUS_ACTIVE,
    "leave": UserCommunityStatus.STATUS_ON_LEAVE,
    "restore": UserCommunityStatus.STATUS_ACTIVE,
}

DEFAULT_REASONS = {
    "promote": "Promoted from trial via alliance health",
    "leave": "Put on leave via alliance health",
    "restore": "Taken off leave via alliance health",
}

# Which current statuses each action may start from (leave: any).
_FROM_STATUSES = {
    "promote": {UserCommunityStatus.STATUS_TRIAL},
    "restore": {UserCommunityStatus.STATUS_ON_LEAVE},
}

_TRANSITION_ERRORS = {
    "promote": "Promote is only valid for members currently on trial",
    "restore": "Restore is only valid for members currently on leave",
}

# Statuses a list offers "Put on leave" for.
_OFFER_LEAVE_FROM = {
    UserCommunityStatus.STATUS_ACTIVE,
    UserCommunityStatus.STATUS_TRIAL,
}


@dataclass
class StatusChangeResult:
    code: int
    status: str | None = None
    error: str | None = None


def current_status(user: User) -> str | None:
    return (
        UserCommunityStatus.objects.filter(user=user)
        .values_list("status", flat=True)
        .first()
    )


def can_change_status(actor: User, target: User, action: str) -> bool:
    if action == "leave":
        return can_put_on_leave(actor, target)
    return can_mutate_status(actor, target)


def available_actions(
    actor: User, target: User, status: str | None
) -> list[str]:
    """Leave/restore actions the actor may take on the target right now."""
    offered = {
        "restore": status in _FROM_STATUSES["restore"],
        "leave": status in _OFFER_LEAVE_FROM,
    }
    return [
        action
        for action, offer in offered.items()
        if offer and can_change_status(actor, target, action)
    ]


def change_community_status(
    actor: User, target: User, action: str, reason: str = ""
) -> StatusChangeResult:
    if action not in ACTIONS:
        return StatusChangeResult(
            400, error="action must be promote, leave, or restore"
        )
    if not can_change_status(actor, target, action):
        return StatusChangeResult(
            403,
            error="Not allowed to change this member's community status",
        )
    current = current_status(target)
    allowed_from = _FROM_STATUSES.get(action)
    if allowed_from is not None and current not in allowed_from:
        return StatusChangeResult(400, error=_TRANSITION_ERRORS[action])
    new_status = ACTIONS[action]
    reason = (reason or "").strip() or DEFAULT_REASONS[action]
    applied, _, error = process_bulk_community_status_row(
        {
            "username": target.username,
            "community_status": new_status,
            "reason": reason,
        },
        1,
        reason,
        changed_by_user_id=actor.id,
    )[:3]
    if error:
        return StatusChangeResult(400, error=error)
    if not applied:
        return StatusChangeResult(400, error="Status was not applied")
    apply_status_change_to_latest_snapshot(target.id, action, current)
    return StatusChangeResult(200, status=new_status)
