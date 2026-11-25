"""Promote, put on leave, make alumni, or restore: one path for every screen.

The alliance health lists and the corp Members tab both change a member's
community status through here, so they share the same permission checks
(``can_put_on_leave`` for leave and alumni, ``can_mutate_status``
otherwise), the same allowed transitions and the same snapshot patch.

Alumni are pilots who aren't coming back. The CEO writes why (an
achievement, what they did for the alliance); that write-up is required,
is kept in the status history, and is sent to the pilot on Discord.
"""

import logging
from dataclasses import dataclass

from django.contrib.auth.models import User

from alliance.helpers.access import can_mutate_status, can_put_on_leave
from alliance.helpers.health_snapshot_patch import (
    apply_status_change_to_latest_snapshot,
)
from discord.models import DiscordUser
from discord.outbox import queue_dm
from eveonline.helpers.characters import user_primary_character
from groups.helpers import process_bulk_community_status_row
from groups.models import UserCommunityStatus

logger = logging.getLogger(__name__)

ACTIONS = {
    "promote": UserCommunityStatus.STATUS_ACTIVE,
    "leave": UserCommunityStatus.STATUS_ON_LEAVE,
    "alumni": UserCommunityStatus.STATUS_ALUMNI,
    "restore": UserCommunityStatus.STATUS_ACTIVE,
}

DEFAULT_REASONS = {
    "promote": "Promoted from trial via alliance health",
    "leave": "Put on leave via alliance health",
    "restore": "Restored to active via alliance health",
}

# The CEO's write-up is the point of alumni status: no default.
ALUMNI_REASON_MAX = 1000

# Which current statuses each action may start from (leave: any).
_FROM_STATUSES = {
    "promote": {UserCommunityStatus.STATUS_TRIAL},
    "alumni": {
        UserCommunityStatus.STATUS_ACTIVE,
        UserCommunityStatus.STATUS_TRIAL,
        UserCommunityStatus.STATUS_ON_LEAVE,
    },
    "restore": {
        UserCommunityStatus.STATUS_ON_LEAVE,
        UserCommunityStatus.STATUS_ALUMNI,
    },
}

_TRANSITION_ERRORS = {
    "promote": "Promote is only valid for members currently on trial",
    "alumni": "This member is already alumni",
    "restore": "Restore is only valid for members on leave or alumni",
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


def can_change_status(
    actor: User, target: User, action: str, status: str | None = None
) -> bool:
    """Leave and alumni are the CEO's call (or a superuser's); so is taking
    someone off alumni. Everything else: officers and the People team."""
    if action in ("leave", "alumni"):
        return can_put_on_leave(actor, target)
    if action == "restore" and status == UserCommunityStatus.STATUS_ALUMNI:
        return can_put_on_leave(actor, target)
    return can_mutate_status(actor, target)


def available_actions(
    actor: User, target: User, status: str | None
) -> list[str]:
    """Leave/alumni/restore actions the actor may take on the target now.

    A pilot with no status row reads as active for alumni, but is still not
    offered leave (as before alumni existed)."""
    offered = {
        "restore": status in _FROM_STATUSES["restore"],
        "leave": status in _OFFER_LEAVE_FROM,
        "alumni": (status or UserCommunityStatus.STATUS_ACTIVE)
        in _FROM_STATUSES["alumni"],
    }
    return [
        action
        for action, offer in offered.items()
        if offer and can_change_status(actor, target, action, status)
    ]


def change_community_status(
    actor: User, target: User, action: str, reason: str = ""
) -> StatusChangeResult:
    if action not in ACTIONS:
        return StatusChangeResult(
            400, error="action must be promote, leave, alumni, or restore"
        )
    current = current_status(target)
    if not can_change_status(actor, target, action, current):
        return StatusChangeResult(
            403,
            error="Not allowed to change this member's community status",
        )
    allowed_from = _FROM_STATUSES.get(action)
    effective = current or UserCommunityStatus.STATUS_ACTIVE
    if allowed_from is not None and effective not in allowed_from:
        return StatusChangeResult(400, error=_TRANSITION_ERRORS[action])
    new_status = ACTIONS[action]
    reason = (reason or "").strip()
    if action == "alumni":
        if not reason:
            return StatusChangeResult(
                400, error="Write why this member is becoming alumni"
            )
        if len(reason) > ALUMNI_REASON_MAX:
            return StatusChangeResult(
                400,
                error=f"Keep the write-up under {ALUMNI_REASON_MAX} characters",
            )
    reason = reason or DEFAULT_REASONS[action]
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
    if action == "alumni":
        notify_alumni(actor, target, reason)
    return StatusChangeResult(200, status=new_status)


def _pilot_name(user: User) -> str:
    primary = user_primary_character(user)
    if primary is not None and primary.character_name:
        return primary.character_name
    return user.username


def alumni_message(actor: User, target: User, reason: str) -> str:
    quoted = "\n".join(f"> {line}" for line in reason.splitlines() if line)
    return (
        f"**{_pilot_name(target)}, you are now Minmatar Fleet Alumni.**\n\n"
        f"{_pilot_name(actor)} wrote:\n{quoted}\n\n"
        "Thank you for everything you did for the alliance. Alumni keep "
        "their place in our history: you won't be removed in activity "
        "cleanups and you no longer count toward alliance activity. "
        "Fly safe, and you're always welcome to say hello."
    )


def notify_alumni(actor: User, target: User, reason: str) -> bool:
    """Queue the alumni DM. False when the pilot has no Discord linked."""
    discord_id = (
        DiscordUser.objects.filter(user=target)
        .values_list("id", flat=True)
        .first()
    )
    if not discord_id:
        logger.info("No alumni DM for %s (no Discord link)", target.username)
        return False
    queue_dm(
        discord_id,
        message=alumni_message(actor, target, reason),
        context=f"alumni status for {target.username}",
    )
    return True
