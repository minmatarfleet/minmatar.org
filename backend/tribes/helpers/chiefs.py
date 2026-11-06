"""Who leads a tribe or group, and filling a seat that has no chief.

A group without a chief is led by its tribe chief, as interim chief. A tribe
without a chief, and any chiefless group in it, is led by the alliance
executor (settings.ALLIANCE_EXECUTOR_CHARACTER_ID), also as interim. Pages
show Help wanted whenever the chief shown is interim.

Interim is display only: it grants no chief permissions.

Pilots volunteer for an open seat; the executor gets a DM and appoints one
(or says not now), from the DM or the website.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from app.links import site_url
from eveonline.models import EveCharacter
from notifications.service import notify_user
from notifications.types.tribes import TRIBE_CHIEF_VOLUNTEERED_KEY
from tribes.models import (
    Tribe,
    TribeChiefVolunteer,
    TribeGroup,
    TribeGroupMembership,
)

logger = logging.getLogger(__name__)


class ChiefVolunteerError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ActingChief:
    """The pilot shown as chief, and whether they only stand in."""

    user: object | None
    is_interim: bool


def executor_user():
    """The site user who owns the executor character, or None."""
    character_id = getattr(settings, "ALLIANCE_EXECUTOR_CHARACTER_ID", 0)
    if not character_id:
        return None
    character = (
        EveCharacter.objects.select_related(
            "user__eveplayer__primary_character",
            "token__user__eveplayer__primary_character",
        )
        .filter(character_id=character_id)
        .first()
    )
    if character is None:
        return None
    if character.user_id:
        return character.user
    token = character.token
    return token.user if token and token.user_id else None


class ChiefResolver:
    """Resolves acting chiefs, looking the executor up at most once."""

    def __init__(self):
        self._executor_loaded = False
        self._executor = None

    @property
    def executor(self):
        if not self._executor_loaded:
            self._executor = executor_user()
            self._executor_loaded = True
        return self._executor

    def for_tribe(self, tribe: Tribe) -> ActingChief:
        if tribe.chief_id:
            return ActingChief(tribe.chief, False)
        return ActingChief(self.executor, True)

    def for_group(self, tribe_group: TribeGroup) -> ActingChief:
        if tribe_group.chief_id:
            return ActingChief(tribe_group.chief, False)
        return ActingChief(self.for_tribe(tribe_group.tribe).user, True)


def user_is_executor(user, resolver: ChiefResolver | None = None) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    executor = (resolver or ChiefResolver()).executor
    return executor is not None and executor.pk == user.pk


def seat_is_open(tribe: Tribe, tribe_group: TribeGroup | None) -> bool:
    if tribe_group is not None:
        return not tribe_group.chief_id
    return not tribe.chief_id


def seat_name(offer: TribeChiefVolunteer) -> str:
    if offer.tribe_group_id:
        return offer.tribe_group.name
    return offer.tribe.name


def seat_page_url(tribe: Tribe, tribe_group: TribeGroup | None) -> str:
    """Where the executor reviews a seat's volunteers."""
    if tribe_group is not None:
        return site_url(
            f"/alliance/tribes/{tribe.pk}/{tribe_group.pk}/#chief-volunteers"
        )
    return site_url(f"/alliance/tribes/{tribe.pk}/#chief-volunteers")


def display_name(user) -> str:
    if user is None:
        return "A pilot"
    player = getattr(user, "eveplayer", None)
    primary = getattr(player, "primary_character", None) if player else None
    if primary and primary.character_name:
        return primary.character_name
    return user.username


def pending_volunteers(tribe: Tribe, tribe_group: TribeGroup | None):
    return (
        TribeChiefVolunteer.objects.filter(
            tribe=tribe,
            tribe_group=tribe_group,
            status=TribeChiefVolunteer.STATUS_PENDING,
        )
        .select_related("user__eveplayer__primary_character")
        .order_by("created_at")
    )


def has_pending_offer(user, tribe: Tribe, tribe_group) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return TribeChiefVolunteer.objects.filter(
        tribe=tribe,
        tribe_group=tribe_group,
        user_id=user.pk,
        status=TribeChiefVolunteer.STATUS_PENDING,
    ).exists()


def volunteer(
    user, tribe: Tribe, tribe_group: TribeGroup | None, note: str = ""
) -> TribeChiefVolunteer:
    """Offer to lead an open seat; DMs the executor."""
    note = (note or "").strip()
    if len(note) > TribeChiefVolunteer.NOTE_MAX_LENGTH:
        raise ChiefVolunteerError(
            f"Keep the note under {TribeChiefVolunteer.NOTE_MAX_LENGTH} "
            "characters."
        )
    if not tribe.is_active or (
        tribe_group is not None and not tribe_group.is_active
    ):
        raise ChiefVolunteerError("That group isn't active.", status_code=404)
    if not seat_is_open(tribe, tribe_group):
        raise ChiefVolunteerError("This seat already has a chief.")
    executor = executor_user()
    if executor is None:
        raise ChiefVolunteerError(
            "No executor is set up to review volunteers.", status_code=503
        )
    if has_pending_offer(user, tribe, tribe_group):
        raise ChiefVolunteerError("You've already volunteered for this.")

    with transaction.atomic():
        offer = TribeChiefVolunteer.objects.create(
            tribe=tribe, tribe_group=tribe_group, user=user, note=note
        )
        transaction.on_commit(lambda: _notify_executor(offer, executor))
    return offer


def volunteered_delivery_key(offer: TribeChiefVolunteer) -> str:
    """The notify idempotency key; the service appends ``:u<user id>``."""
    return f"tribes.chief_volunteered:{offer.pk}"


def _notify_executor(offer: TribeChiefVolunteer, executor) -> None:
    tribe = offer.tribe
    tribe_group = offer.tribe_group
    interim = (
        ChiefResolver().for_group(tribe_group).user
        if tribe_group is not None
        else executor
    )
    try:
        notify_user(
            executor,
            TRIBE_CHIEF_VOLUNTEERED_KEY,
            {
                "volunteer_id": offer.pk,
                "pilot": display_name(offer.user),
                "seat_name": seat_name(offer),
                "tribe_name": tribe.name,
                "is_tribe_seat": tribe_group is None,
                "interim": display_name(interim) if interim else "",
                "note": offer.note,
                "url": seat_page_url(tribe, tribe_group),
            },
            idempotency_key=volunteered_delivery_key(offer),
        )
    except Exception:  # pylint: disable=broad-except
        logger.warning(
            "Failed to queue chief volunteer notification %s",
            offer.pk,
            exc_info=True,
        )


def _require_executor(user) -> None:
    if not user_is_executor(user):
        raise ChiefVolunteerError(
            "Only the alliance executor appoints chiefs.", status_code=403
        )


def _require_pending(offer: TribeChiefVolunteer) -> None:
    if offer.status != TribeChiefVolunteer.STATUS_PENDING:
        raise ChiefVolunteerError("That offer was already answered.")


def _activate_membership(user, tribe_group: TribeGroup, by) -> None:
    """A new group chief is an active member, like tribe chiefs are."""
    now = timezone.now()
    membership, created = TribeGroupMembership.objects.get_or_create(
        user=user,
        tribe_group=tribe_group,
        defaults={
            "status": TribeGroupMembership.STATUS_ACTIVE,
            "approved_at": now,
            "approved_by": by,
        },
    )
    if created or membership.status == TribeGroupMembership.STATUS_ACTIVE:
        return
    membership.status = TribeGroupMembership.STATUS_ACTIVE
    membership.approved_at = now
    membership.approved_by = by
    membership.left_at = None
    membership.removed_by = None
    membership.history_changed_by = by
    membership.history_inactive_reason = ""
    membership.save()


def appoint(offer: TribeChiefVolunteer, by) -> TribeChiefVolunteer:
    """Make the volunteer chief; close the seat's other open offers."""
    # pylint: disable-next=import-outside-toplevel
    from tribes.helpers.chief_membership import (
        ensure_tribe_chiefs_have_group_memberships,
    )

    _require_executor(by)
    _require_pending(offer)
    tribe = offer.tribe
    tribe_group = offer.tribe_group
    if not seat_is_open(tribe, tribe_group):
        raise ChiefVolunteerError("This seat already has a chief.")

    now = timezone.now()
    with transaction.atomic():
        if tribe_group is not None:
            tribe_group.chief = offer.user
            tribe_group.save(update_fields=["chief"])
            _activate_membership(offer.user, tribe_group, by)
        else:
            tribe.chief = offer.user
            tribe.save(update_fields=["chief", "updated_at"])
        offer.status = TribeChiefVolunteer.STATUS_APPOINTED
        offer.decided_at = now
        offer.decided_by = by
        offer.save(update_fields=["status", "decided_at", "decided_by"])
        others = list(
            pending_volunteers(tribe, tribe_group).exclude(pk=offer.pk)
        )
        TribeChiefVolunteer.objects.filter(
            pk__in=[o.pk for o in others]
        ).update(
            status=TribeChiefVolunteer.STATUS_CLOSED,
            decided_at=now,
            decided_by=by,
        )
        for changed in [offer, *others]:
            _queue_dm_update(changed)
    if tribe_group is None:
        ensure_tribe_chiefs_have_group_memberships()
    return offer


def decline(offer: TribeChiefVolunteer, by) -> TribeChiefVolunteer:
    """Not now: the seat stays open."""
    _require_executor(by)
    _require_pending(offer)
    offer.status = TribeChiefVolunteer.STATUS_DECLINED
    offer.decided_at = timezone.now()
    offer.decided_by = by
    with transaction.atomic():
        offer.save(update_fields=["status", "decided_at", "decided_by"])
        _queue_dm_update(offer)
    return offer


def _queue_dm_update(offer: TribeChiefVolunteer) -> None:
    """Edit the executor's DM once the offer is answered."""
    # pylint: disable-next=import-outside-toplevel
    from discord.outbox import on_commit_enqueue

    # pylint: disable-next=import-outside-toplevel
    from tribes.tasks import update_chief_volunteer_dm

    on_commit_enqueue(
        update_chief_volunteer_dm,
        args=(offer.pk,),
        context=f"chief volunteer {offer.pk}",
    )


def answered_dm(offer: TribeChiefVolunteer) -> dict:
    """Title and text the executor's DM is edited to."""
    pilot = display_name(offer.user)
    seat = seat_name(offer)
    if offer.status == TribeChiefVolunteer.STATUS_APPOINTED:
        return {
            "title": f"{pilot} is now chief of {seat}",
            "description": "Appointed. The Help wanted banner is gone.",
            "colored": True,
        }
    if offer.status == TribeChiefVolunteer.STATUS_CLOSED:
        return {
            "title": f"{seat} has a chief now",
            "description": f"{pilot}'s offer was closed.",
        }
    return {
        "title": f"Not now: {pilot} for {seat}",
        "description": "The seat stays open.",
    }
