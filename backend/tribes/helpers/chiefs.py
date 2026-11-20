"""Who leads a tribe or group, and filling a seat that has no chief.

A tribe has one chief. A group has up to three, one per timezone seat
(US, EU, AU; tribes.models.TribeGroupChief), and every seated chief leads
it. A group with no seat filled is led by its tribe chief, as interim chief. A tribe
without a chief, and any chiefless group in it, is led by the alliance
executor (settings.ALLIANCE_EXECUTOR_CHARACTER_ID), also as interim. Pages
show Help wanted whenever the chief shown is interim.

An interim chief acts as chief: applications notify them, they manage
membership, and help tickets and reminders ping them
(tribes.helpers.permissions, groups.helpers.feature_access).

Pilots volunteer for an open seat; the executor gets a DM and appoints one
(or says not now), from the DM or the website.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from app.links import site_url
from eveonline.models import EveCharacter
from notifications.service import notify_user
from notifications.types.tribes import TRIBE_CHIEF_VOLUNTEERED_KEY
from timezones.services import timezone_for
from tribes.helpers.chief_regions import (
    LABELS as REGION_LABELS,
    REGIONS,
    clean_region,
    home_region,
    pick_region,
)
from tribes.models import (
    Tribe,
    TribeChiefVolunteer,
    TribeGroup,
    TribeGroupChief,
    TribeGroupMembership,
)

logger = logging.getLogger(__name__)


class ChiefVolunteerError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ActingChief:
    """The pilot shown as chief, and whether they only stand in.

    ``users`` is everyone who leads the seat: every seated group chief, or
    the one stand-in. ``user`` is the first of them.
    """

    user: object | None
    is_interim: bool
    users: tuple = field(default=())


def group_seats(tribe_group: TribeGroup) -> list[TribeGroupChief]:
    """The group's filled seats in US, EU, AU order (uses a prefetch)."""
    seats = list(tribe_group.chief_seats.all())
    seats.sort(key=lambda seat: REGIONS.index(seat.region))
    return seats


def group_chief_ids(tribe_group: TribeGroup) -> set[int]:
    return {seat.user_id for seat in tribe_group.chief_seats.all()}


def user_region(user) -> str | None:
    """The pilot's timezone region, from the timezones app."""
    if user is None:
        return None
    row = timezone_for(user.pk)
    return home_region(row.home, row.brackets) if row else None


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
            return ActingChief(tribe.chief, False, (tribe.chief,))
        executor = self.executor
        return ActingChief(executor, True, (executor,) if executor else ())

    def for_group(self, tribe_group: TribeGroup) -> ActingChief:
        seats = group_seats(tribe_group)
        if seats:
            users = tuple(seat.user for seat in seats)
            return ActingChief(users[0], False, users)
        stand_in = self.for_tribe(tribe_group.tribe).user
        return ActingChief(stand_in, True, (stand_in,) if stand_in else ())


def user_is_executor(user, resolver: ChiefResolver | None = None) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    executor = (resolver or ChiefResolver()).executor
    return executor is not None and executor.pk == user.pk


def open_regions(tribe_group: TribeGroup) -> list[str]:
    taken = set(
        TribeGroupChief.objects.filter(tribe_group=tribe_group).values_list(
            "region", flat=True
        )
    )
    return [region for region in REGIONS if region not in taken]


def seat_is_open(
    tribe: Tribe, tribe_group: TribeGroup | None, region: str | None = None
) -> bool:
    """A group seat is open when ``region`` (or, without one, any of its
    three seats) has no chief."""
    if tribe_group is not None:
        regions = open_regions(tribe_group)
        return region in regions if region else bool(regions)
    return not tribe.chief_id


def seat_label(name: str, region: str | None) -> str:
    return f"{name} ({REGION_LABELS[region]})" if region else name


def seat_name(offer: TribeChiefVolunteer) -> str:
    if offer.tribe_group_id:
        return seat_label(offer.tribe_group.name, offer.region or None)
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


def pending_volunteers(
    tribe: Tribe, tribe_group: TribeGroup | None, region: str | None = None
):
    """A seat's open offers; a group without ``region`` lists all three."""
    offers = TribeChiefVolunteer.objects.filter(
        tribe=tribe,
        tribe_group=tribe_group,
        status=TribeChiefVolunteer.STATUS_PENDING,
    )
    if tribe_group is not None and region:
        offers = offers.filter(region=region)
    return offers.select_related(
        "user__eveplayer__primary_character"
    ).order_by("created_at")


def has_pending_offer(user, tribe: Tribe, tribe_group) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return TribeChiefVolunteer.objects.filter(
        tribe=tribe,
        tribe_group=tribe_group,
        user_id=user.pk,
        status=TribeChiefVolunteer.STATUS_PENDING,
    ).exists()


def _volunteer_region(user, tribe_group: TribeGroup, region) -> str:
    """The group seat an offer is for: the asked one, else the pilot's own
    timezone when free, else the first free seat."""
    if region:
        asked = clean_region(region)
        if asked is None:
            raise ChiefVolunteerError("Pick the US, EU or AU seat.")
        if not seat_is_open(tribe_group.tribe, tribe_group, asked):
            raise ChiefVolunteerError(
                f"The {REGION_LABELS[asked]} seat already has a chief."
            )
        return asked
    taken = set(REGIONS) - set(open_regions(tribe_group))
    picked = pick_region(user_region(user), taken)
    if picked is None:
        raise ChiefVolunteerError("Every seat already has a chief.")
    return picked


def volunteer(
    user,
    tribe: Tribe,
    tribe_group: TribeGroup | None,
    note: str = "",
    region: str | None = None,
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
    seat_region = ""
    if tribe_group is not None:
        if user.pk in group_chief_ids(tribe_group):
            raise ChiefVolunteerError("You're already a chief of this group.")
        seat_region = _volunteer_region(user, tribe_group, region)
    elif not seat_is_open(tribe, tribe_group):
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
            tribe=tribe,
            tribe_group=tribe_group,
            region=seat_region,
            user=user,
            note=note,
        )
        transaction.on_commit(lambda: _notify_executor(offer, executor))
    return offer


def volunteered_delivery_key(offer: TribeChiefVolunteer) -> str:
    """The notify idempotency key; the service appends ``:u<user id>``."""
    return f"tribes.chief_volunteered:{offer.pk}"


def _notify_executor(offer: TribeChiefVolunteer, executor) -> None:
    tribe = offer.tribe
    tribe_group = offer.tribe_group
    interim = executor
    if tribe_group is not None:
        acting = ChiefResolver().for_group(tribe_group)
        # Another timezone's chief isn't standing in; they lead already.
        interim = acting.user if acting.is_interim else None
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


def _lock_pending(offer: TribeChiefVolunteer) -> None:
    """Lock the offer row and check it's still waiting (inside atomic)."""
    status = (
        TribeChiefVolunteer.objects.select_for_update()
        .values_list("status", flat=True)
        .get(pk=offer.pk)
    )
    offer.status = status
    _require_pending(offer)


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
    now = timezone.now()
    with transaction.atomic():
        # Lock the offer and the seat so a double click (the DM button and
        # the website) can't appoint two chiefs.
        _lock_pending(offer)
        tribe = Tribe.objects.select_for_update().get(pk=offer.tribe_id)
        tribe_group = (
            TribeGroup.objects.select_for_update().get(pk=offer.tribe_group_id)
            if offer.tribe_group_id
            else None
        )
        region = offer.region or None
        if tribe_group is not None and region is None:
            region = pick_region(
                user_region(offer.user),
                set(REGIONS) - set(open_regions(tribe_group)),
            )
        if not seat_is_open(tribe, tribe_group, region):
            raise ChiefVolunteerError("This seat already has a chief.")
        if tribe_group is not None:
            if offer.user_id in group_chief_ids(tribe_group):
                raise ChiefVolunteerError(
                    "They're already a chief of this group."
                )
            TribeGroupChief.objects.create(
                tribe_group=tribe_group, region=region, user=offer.user
            )
            offer.region = region
            _activate_membership(offer.user, tribe_group, by)
        else:
            tribe.chief = offer.user
            tribe.save(update_fields=["chief", "updated_at"])
        offer.status = TribeChiefVolunteer.STATUS_APPOINTED
        offer.decided_at = now
        offer.decided_by = by
        offer.save(
            update_fields=["status", "decided_at", "decided_by", "region"]
        )
        # The seat's other offers, and the new chief's offers for the
        # group's other seats.
        others = [
            other
            for other in pending_volunteers(tribe, tribe_group)
            if other.pk != offer.pk
            and (
                tribe_group is None
                or other.region == offer.region
                or other.user_id == offer.user_id
            )
        ]
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
        # The chief is saved; group memberships follow. A failed Discord
        # role sync here is retried by the scheduled membership task.
        try:
            ensure_tribe_chiefs_have_group_memberships()
        except Exception:  # pylint: disable=broad-except
            logger.warning(
                "Group memberships for new tribe chief %s failed",
                offer.user_id,
                exc_info=True,
            )
    offer.tribe = tribe
    offer.tribe_group = tribe_group
    return offer


def _set_group_seat(by, tribe_group: TribeGroup, region: str, user):
    """Fill or empty one group seat; returns the pilot who held it.

    A pilot already in another of the group's seats moves to this one.
    """
    current = (
        TribeGroupChief.objects.select_related("user")
        .filter(tribe_group=tribe_group, region=region)
        .first()
    )
    old = current.user if current else None
    if (old.pk if old else None) == (user.pk if user else None):
        return old, False
    if current is not None:
        current.delete()
    if user is not None:
        TribeGroupChief.objects.filter(
            tribe_group=tribe_group, user=user
        ).delete()
        TribeGroupChief.objects.create(
            tribe_group=tribe_group, region=region, user=user
        )
        _activate_membership(user, tribe_group, by)
    return old, True


def _swap_region(user, region) -> str:
    """The group seat a superuser swap targets."""
    seat_region = clean_region(region) if region else None
    if region and seat_region is None:
        raise ChiefVolunteerError("Pick the US, EU or AU seat.")
    if seat_region is None and user is not None:
        seat_region = user_region(user) or REGIONS[0]
    if seat_region is None:
        raise ChiefVolunteerError("Say which seat to empty.")
    return seat_region


def set_chief(
    by,
    tribe: Tribe,
    tribe_group: TribeGroup | None,
    user,
    region: str | None = None,
) -> object | None:
    """Superuser override: put ``user`` in the seat, or empty it (None).

    A group seat is one of its timezone seats: ``region`` (US, EU, AU),
    defaulting to the pilot's own timezone when filling one.

    Unlike ``appoint`` this works on a filled seat and needs no volunteer.
    The old chief keeps their group memberships. Waiting offers are closed
    when the seat is filled, as an appointment does.
    """
    # pylint: disable-next=import-outside-toplevel
    from audit.helpers import record_audit

    # pylint: disable-next=import-outside-toplevel
    from tribes.helpers.chief_membership import (
        ensure_tribe_chiefs_have_group_memberships,
    )

    if by is None or not getattr(by, "is_superuser", False):
        raise ChiefVolunteerError(
            "Only superusers can swap a chief.", status_code=403
        )
    seat_region = (
        _swap_region(user, region) if tribe_group is not None else None
    )
    now = timezone.now()
    with transaction.atomic():
        tribe = Tribe.objects.select_for_update().get(pk=tribe.pk)
        if tribe_group is not None:
            tribe_group = TribeGroup.objects.select_for_update().get(
                pk=tribe_group.pk
            )
            old, changed = _set_group_seat(by, tribe_group, seat_region, user)
            label = seat_label(tribe_group.name, seat_region)
        else:
            old = tribe.chief
            changed = (old.pk if old else None) != (user.pk if user else None)
            if changed:
                tribe.chief = user
                tribe.save(update_fields=["chief", "updated_at"])
            label = tribe.name
        if not changed:
            return user
        others = []
        if user is not None:
            others = [
                offer
                for offer in pending_volunteers(tribe, tribe_group)
                if tribe_group is None
                or offer.region == seat_region
                or offer.user_id == user.pk
            ]
            TribeChiefVolunteer.objects.filter(
                pk__in=[o.pk for o in others]
            ).update(
                status=TribeChiefVolunteer.STATUS_CLOSED,
                decided_at=now,
                decided_by=by,
            )
            for changed_offer in others:
                changed_offer.status = TribeChiefVolunteer.STATUS_CLOSED
                _queue_dm_update(changed_offer)
        record_audit(
            by,
            f"Chief of {label}: {display_name(old) if old else 'nobody'}"
            f" -> {display_name(user) if user else 'nobody'}",
            "other",
        )
    if tribe_group is None and user is not None:
        try:
            ensure_tribe_chiefs_have_group_memberships()
        except Exception:  # pylint: disable=broad-except
            logger.warning(
                "Group memberships for new tribe chief %s failed",
                user.pk,
                exc_info=True,
            )
    return user


def decline(offer: TribeChiefVolunteer, by) -> TribeChiefVolunteer:
    """Not now: the seat stays open."""
    _require_executor(by)
    with transaction.atomic():
        _lock_pending(offer)
        offer.status = TribeChiefVolunteer.STATUS_DECLINED
        offer.decided_at = timezone.now()
        offer.decided_by = by
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
