"""Tribe group invitations: who can be invited, sending, and answers.

A chief invites a pilot; the pilot accepts on the group page (picking
characters, as applying does) and is active at once, with the inviter as
approver. Endpoints stay thin and call these helpers.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from app.links import site_url
from eveonline.models import EveCharacter
from groups.helpers.feature_access import can_use_feature
from notifications.service import notify_user
from notifications.types.tribes import (
    TRIBE_INVITE_ANSWERED_KEY,
    TRIBE_INVITED_KEY,
)
from tribes.helpers.requirements import build_membership_snapshot
from tribes.helpers.token_requirements import (
    characters_missing_required_token,
    token_requirement_error_detail,
)
from tribes.helpers.trial_requirements import (
    OFF_TRIAL_REQUIRED_DETAIL,
    application_blocked_by_trial,
)
from tribes.models import (
    TribeGroup,
    TribeGroupInvitation,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
    TribeGroupMembershipCharacterHistory,
)

logger = logging.getLogger(__name__)

EXPIRY_DAYS = 14
REINVITE_WAIT_DAYS = 30
MAX_INVITES_PER_SEND = 10

# Why a pilot can't be invited (``invite_blocker``).
BLOCK_MEMBER = "member"
BLOCK_APPLIED = "applied"
BLOCK_INVITED = "invited"
BLOCK_DECLINED = "declined_recently"
BLOCK_TRIAL = "on_trial"
BLOCK_NOT_ELIGIBLE = "not_eligible"

ANSWERED_STATUSES = (
    TribeGroupInvitation.STATUS_ACCEPTED,
    TribeGroupInvitation.STATUS_DECLINED,
    TribeGroupInvitation.STATUS_WITHDRAWN,
    TribeGroupInvitation.STATUS_EXPIRED,
)


class InvitationError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def short_date(value) -> str:
    """ "Nov 6" (no leading zero, no year)."""
    return f"{value:%b} {value.day}"


def long_date(value) -> str:
    """ "Fri, Nov 6"."""
    return f"{value:%a}, {short_date(value)}"


def group_page_url(tribe_group: TribeGroup) -> str:
    return site_url(
        f"/alliance/tribes/{tribe_group.tribe_id}/{tribe_group.pk}/"
    )


def members_page_url(tribe_group: TribeGroup) -> str:
    return site_url(
        f"/alliance/tribes/{tribe_group.tribe_id}/{tribe_group.pk}/members"
    )


def effective_status(invitation: TribeGroupInvitation, now=None) -> str:
    """Pending invites past their expiry read as expired before the
    daily sweep marks them."""
    now = now or timezone.now()
    if (
        invitation.status == TribeGroupInvitation.STATUS_PENDING
        and invitation.expires_at <= now
    ):
        return TribeGroupInvitation.STATUS_EXPIRED
    return invitation.status


def open_invitation(user, tribe_group: TribeGroup):
    """The pilot's live invite to this group, or None."""
    return (
        TribeGroupInvitation.objects.filter(
            user=user,
            tribe_group=tribe_group,
            status=TribeGroupInvitation.STATUS_PENDING,
            expires_at__gt=timezone.now(),
        )
        .select_related("invited_by__eveplayer__primary_character")
        .order_by("-created_at")
        .first()
    )


def invite_blocker(user, tribe_group: TribeGroup, now=None):
    """Why ``user`` can't be invited to ``tribe_group``, or None.

    Returns ``(code, detail)`` where detail carries what the picker shows
    (the application id, or the date a decline wait ends).
    """
    now = now or timezone.now()
    membership = TribeGroupMembership.objects.filter(
        user=user, tribe_group=tribe_group
    ).first()
    if membership and membership.status == TribeGroupMembership.STATUS_ACTIVE:
        return BLOCK_MEMBER, {}
    if membership and membership.status == TribeGroupMembership.STATUS_PENDING:
        return BLOCK_APPLIED, {
            "membership_id": membership.pk,
            "since": membership.created_at,
        }
    invites = TribeGroupInvitation.objects.filter(
        user=user, tribe_group=tribe_group
    )
    if invites.filter(
        status=TribeGroupInvitation.STATUS_PENDING, expires_at__gt=now
    ).exists():
        return BLOCK_INVITED, {}
    declined = (
        invites.filter(
            status=TribeGroupInvitation.STATUS_DECLINED,
            responded_at__gt=now - timedelta(days=REINVITE_WAIT_DAYS),
        )
        .order_by("-responded_at")
        .first()
    )
    if declined:
        return BLOCK_DECLINED, {
            "until": declined.responded_at + timedelta(days=REINVITE_WAIT_DAYS)
        }
    if application_blocked_by_trial(user, tribe_group):
        return BLOCK_TRIAL, {}
    if not can_use_feature(user, "tribes.apply", tribe_group=tribe_group):
        return BLOCK_NOT_ELIGIBLE, {}
    return None


def requirements_summary(tribe_group: TribeGroup) -> str:
    """One line for the DM: "Revelation, Revelation Navy Issue or
    Zirnitra · off trial"."""
    ships: list[str] = []
    skills: list[str] = []
    for requirement in tribe_group.requirements.prefetch_related(
        "asset_types__eve_type", "qualifying_skills__eve_type"
    ):
        for asset in requirement.asset_types.all():
            if asset.eve_type and asset.eve_type.name not in ships:
                ships.append(asset.eve_type.name)
        for skill in requirement.qualifying_skills.all():
            if skill.eve_type:
                label = f"{skill.eve_type.name} {skill.minimum_level}"
                if label not in skills:
                    skills.append(label)
    parts = []
    if ships:
        parts.append(
            ships[0]
            if len(ships) == 1
            else ", ".join(ships[:-1]) + f" or {ships[-1]}"
        )
    if skills:
        parts.append(", ".join(skills))
    if tribe_group.require_off_trial:
        parts.append("off trial")
    return " · ".join(parts)


def _display_name(user) -> str:
    if user is None:
        return "A chief"
    player = getattr(user, "eveplayer", None)
    primary = getattr(player, "primary_character", None) if player else None
    if primary and primary.character_name:
        return primary.character_name
    return user.username


def send_invitations(
    tribe_group: TribeGroup, users: list, invited_by, note: str = ""
) -> list[TribeGroupInvitation]:
    """Invite each pilot, or raise InvitationError naming who can't be."""
    note = (note or "").strip()
    if len(note) > TribeGroupInvitation.NOTE_MAX_LENGTH:
        raise InvitationError(
            f"Keep the note under {TribeGroupInvitation.NOTE_MAX_LENGTH} "
            "characters."
        )
    if not users:
        raise InvitationError("Pick at least one pilot.")
    if len(users) > MAX_INVITES_PER_SEND:
        raise InvitationError(
            f"Invite at most {MAX_INVITES_PER_SEND} pilots at a time."
        )
    blocked = [u for u in users if invite_blocker(u, tribe_group)]
    if blocked:
        names = ", ".join(_display_name(u) for u in blocked)
        raise InvitationError(f"Can't invite: {names}.")

    now = timezone.now()
    created = []
    with transaction.atomic():
        for user in users:
            invitation = TribeGroupInvitation.objects.create(
                tribe_group=tribe_group,
                user=user,
                invited_by=invited_by,
                note=note,
                expires_at=now + timedelta(days=EXPIRY_DAYS),
            )
            created.append(invitation)
        transaction.on_commit(
            lambda: [_notify_invited(invitation) for invitation in created]
        )
    return created


def invited_delivery_key(invitation: TribeGroupInvitation) -> str:
    """The notify idempotency key; the service appends ``:u<user id>``."""
    return f"tribes.invite:{invitation.pk}"


def _notify_invited(invitation: TribeGroupInvitation) -> None:
    tribe_group = invitation.tribe_group
    try:
        notify_user(
            invitation.user,
            TRIBE_INVITED_KEY,
            {
                "invitation_id": invitation.pk,
                "group_name": tribe_group.name,
                "tribe_name": tribe_group.tribe.name,
                "inviter": _display_name(invitation.invited_by),
                "note": invitation.note,
                "requirements": requirements_summary(tribe_group),
                "expires": long_date(invitation.expires_at),
                "url": group_page_url(tribe_group),
            },
            idempotency_key=invited_delivery_key(invitation),
        )
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "Failed to queue tribe invite notification %s",
            invitation.pk,
            exc_info=True,
        )


def _notify_answered(invitation: TribeGroupInvitation) -> None:
    if invitation.invited_by is None:
        return
    tribe_group = invitation.tribe_group
    accepted = invitation.status == TribeGroupInvitation.STATUS_ACCEPTED
    context = {
        "group_name": tribe_group.name,
        "pilot": _display_name(invitation.user),
        "outcome": "accepted" if accepted else "declined",
        "url": members_page_url(tribe_group),
    }
    if not accepted and invitation.responded_at:
        context["reinvite_after"] = short_date(
            invitation.responded_at + timedelta(days=REINVITE_WAIT_DAYS)
        )
    try:
        notify_user(
            invitation.invited_by,
            TRIBE_INVITE_ANSWERED_KEY,
            context,
            idempotency_key=f"tribes.invite_answered:{invitation.pk}",
        )
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "Failed to queue tribe invite answer notification %s",
            invitation.pk,
            exc_info=True,
        )


def _queue_dm_update(invitation: TribeGroupInvitation) -> None:
    """Edit the invite DM once it's answered: say what happened, drop
    the buttons."""
    # pylint: disable-next=import-outside-toplevel
    from discord.outbox import on_commit_enqueue

    # pylint: disable-next=import-outside-toplevel
    from tribes.tasks import update_tribe_invitation_dm

    on_commit_enqueue(
        update_tribe_invitation_dm,
        args=(invitation.pk,),
        context=f"tribe invite {invitation.pk}",
    )


def _require_pending(invitation: TribeGroupInvitation) -> None:
    status = effective_status(invitation)
    if status == TribeGroupInvitation.STATUS_EXPIRED:
        raise InvitationError("This invite has expired.")
    if status != TribeGroupInvitation.STATUS_PENDING:
        raise InvitationError(f"This invite was already {status}.")


def _commit_characters(membership, user, character_ids: list[int]) -> None:
    for character in EveCharacter.objects.filter(
        character_id__in=character_ids, user=user
    ):
        _, created = TribeGroupMembershipCharacter.objects.get_or_create(
            membership=membership, character=character
        )
        if created:
            TribeGroupMembershipCharacterHistory.objects.create(
                membership=membership,
                character=character,
                action=TribeGroupMembershipCharacterHistory.ACTION_ADDED,
                by=user,
            )


def accept_invitation(
    invitation: TribeGroupInvitation, user, character_ids: list[int]
) -> TribeGroupMembership:
    """Join the group straight away, with the inviter as approver.

    Runs the same checks as applying: off trial when the group needs it,
    and the required ESI token on every picked character.
    """
    if invitation.user_id != user.pk:
        raise InvitationError("This invite isn't yours.", status_code=403)
    _require_pending(invitation)
    tribe_group = invitation.tribe_group
    if not character_ids:
        raise InvitationError("Pick at least one character.")
    owned = list(
        EveCharacter.objects.filter(
            character_id__in=character_ids, user=user
        ).select_related("token")
    )
    if not owned:
        raise InvitationError("Pick at least one of your characters.")
    if application_blocked_by_trial(user, tribe_group):
        raise InvitationError(OFF_TRIAL_REQUIRED_DETAIL)
    missing_token = characters_missing_required_token(owned, tribe_group)
    if missing_token:
        raise InvitationError(
            token_requirement_error_detail(
                missing_token, tribe_group.required_token_type
            )
        )
    picked_ids = [c.character_id for c in owned]

    now = timezone.now()
    with transaction.atomic():
        membership = TribeGroupMembership.objects.filter(
            user=user, tribe_group=tribe_group
        ).first()
        if (
            membership
            and membership.status == TribeGroupMembership.STATUS_ACTIVE
        ):
            raise InvitationError("You're already in this group.")
        if membership is None:
            membership = TribeGroupMembership(
                user=user, tribe_group=tribe_group
            )
        elif membership.status == TribeGroupMembership.STATUS_INACTIVE:
            # Rejoining: the same row goes active again, as re-applying
            # resets it to pending.
            membership.left_at = None
            membership.removed_by = None
            membership.characters.all().delete()
        membership.status = TribeGroupMembership.STATUS_ACTIVE
        membership.requirement_snapshot = build_membership_snapshot(
            user, tribe_group, picked_ids
        )
        membership.approved_by = invitation.invited_by
        membership.approved_at = now
        membership.history_changed_by = user
        membership.save()
        _commit_characters(membership, user, picked_ids)

        invitation.status = TribeGroupInvitation.STATUS_ACCEPTED
        invitation.responded_at = now
        invitation.membership = membership
        invitation.save(update_fields=["status", "responded_at", "membership"])
        transaction.on_commit(lambda: _notify_answered(invitation))
        _queue_dm_update(invitation)
    return membership


def decline_invitation(
    invitation: TribeGroupInvitation, user
) -> TribeGroupInvitation:
    if invitation.user_id != user.pk:
        raise InvitationError("This invite isn't yours.", status_code=403)
    _require_pending(invitation)
    with transaction.atomic():
        invitation.status = TribeGroupInvitation.STATUS_DECLINED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at"])
        transaction.on_commit(lambda: _notify_answered(invitation))
        _queue_dm_update(invitation)
    return invitation


def withdraw_invitation(
    invitation: TribeGroupInvitation,
) -> TribeGroupInvitation:
    _require_pending(invitation)
    with transaction.atomic():
        invitation.status = TribeGroupInvitation.STATUS_WITHDRAWN
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at"])
        _queue_dm_update(invitation)
    return invitation


def expire_due_invitations(now=None) -> int:
    """Mark pending invites past their expiry; edit their DMs."""
    now = now or timezone.now()
    due = list(
        TribeGroupInvitation.objects.filter(
            status=TribeGroupInvitation.STATUS_PENDING, expires_at__lte=now
        )
    )
    for invitation in due:
        with transaction.atomic():
            invitation.status = TribeGroupInvitation.STATUS_EXPIRED
            invitation.responded_at = invitation.expires_at
            invitation.save(update_fields=["status", "responded_at"])
            _queue_dm_update(invitation)
    return len(due)


def answered_dm(invitation: TribeGroupInvitation) -> dict:
    """The embed fields an answered invite DM is edited to."""
    tribe_group = invitation.tribe_group
    inviter = _display_name(invitation.invited_by)
    status = invitation.status
    if status == TribeGroupInvitation.STATUS_ACCEPTED:
        return {
            "title": f"You joined {tribe_group.name}",
            "description": (
                f"You accepted {inviter}’s invite. You have the "
                f"{tribe_group.name} Discord role now."
            ),
            "url": group_page_url(tribe_group),
            "colored": True,
        }
    if status == TribeGroupInvitation.STATUS_DECLINED:
        return {
            "title": f"You declined the invite to {tribe_group.name}",
            "description": f"{inviter} has been told.",
        }
    if status == TribeGroupInvitation.STATUS_WITHDRAWN:
        when = invitation.responded_at or timezone.now()
        return {
            "title": "This invite was withdrawn",
            "description": f"{inviter} withdrew it on {short_date(when)}.",
        }
    return {
        "title": "This invite expired",
        "description": (
            f"It ran out on {short_date(invitation.expires_at)}. You can "
            f"still apply on the {tribe_group.name} page."
        ),
        "url": group_page_url(tribe_group),
    }


def users_by_ids(user_ids: list[int]) -> list:
    found = {
        u.pk: u
        for u in User.objects.filter(pk__in=user_ids).select_related(
            "eveplayer__primary_character"
        )
    }
    return [found[i] for i in dict.fromkeys(user_ids) if i in found]
