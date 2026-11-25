"""Which Mumble fleet holds which of the three fleet branches.

A Mumble fleet leases a free branch when it starts tracking, or from 2 hours
before its start time when it has volunteers or pilots who said in. Without
tracking 30 minutes after start, the lease is released. It ends 30 minutes
after the fleet closes, when the fleet is cancelled, or when the FC switches
its voice away from Mumble. The voice service then kicks whoever is left in
the branch and resets it.

Fleet 1 is the open branch: any community member may join it. A fleet the
FC set to open (``mumble_open``) leases Fleet 1, or a restricted branch
when another open fleet holds it. A restricted fleet leases only Fleet 2 or
3, and loses Fleet 1 if it holds it (``access_changed``).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from fleets.models import (
    EveFleet,
    EveFleetInstance,
    EveFleetInvite,
    FleetVoiceOption,
)
from voice.channels import OPEN_BRANCH
from voice.models import (
    BRANCH_COUNT,
    VoiceAuditEvent,
    VoiceChannelLease,
    VoiceGrant,
)

logger = logging.getLogger(__name__)

EARLY_LEASE = timedelta(hours=2)
NO_TRACKING_TIMEOUT = timedelta(minutes=30)
AFTER_CLOSE = timedelta(minutes=30)
INACTIVE_STATUSES = ("complete", "cancelled")


def _is_tracking(fleet: EveFleet) -> bool:
    return EveFleetInstance.objects.filter(
        eve_fleet=fleet, end_time__isnull=True
    ).exists()


def _has_signups(fleet: EveFleet) -> bool:
    return (
        fleet.role_volunteers.exists()
        or fleet.ship_volunteers.exists()
        or fleet.invites.filter(answer=EveFleetInvite.ANSWER_IN).exists()
    )


def wants_lease(fleet: EveFleet, now=None) -> bool:
    """True when a Mumble fleet should hold a branch right now."""
    now = now or timezone.now()
    if not fleet.uses_mumble or fleet.status in INACTIVE_STATUSES:
        return False
    if _is_tracking(fleet):
        return True
    if fleet.start_time - EARLY_LEASE > now:
        return False
    if now > fleet.start_time + NO_TRACKING_TIMEOUT:
        return False
    return _has_signups(fleet)


def release_reason(lease: VoiceChannelLease, now=None) -> str | None:
    """Why an active lease should end now, or None to keep it."""
    now = now or timezone.now()
    fleet = lease.fleet
    if not fleet.uses_mumble:
        return "voice_changed"
    if fleet.status == "cancelled":
        return "cancelled"
    if lease.branch == OPEN_BRANCH and not fleet.mumble_open:
        # Switched to restricted: a branch everyone can enter won't do.
        return "access_changed"
    if lease.release_after is not None:
        return "closed" if now >= lease.release_after else None
    if _is_tracking(fleet):
        return None
    ever_tracked = EveFleetInstance.objects.filter(eve_fleet=fleet).exists()
    if ever_tracked:
        # Closed without close_fleet_cleanup scheduling it (e.g. ESI lost
        # the fleet): give it the same 30 minutes from its end.
        ended = (
            EveFleetInstance.objects.filter(eve_fleet=fleet)
            .exclude(end_time__isnull=True)
            .order_by("-end_time")
            .values_list("end_time", flat=True)
            .first()
        )
        if ended and now >= ended + AFTER_CLOSE:
            return "closed"
        return None
    if now > fleet.start_time + NO_TRACKING_TIMEOUT:
        return "no_tracking"
    return None


def branch_order(fleet: EveFleet) -> list[int]:
    """The branches a fleet may lease, best first."""
    restricted = [b for b in range(1, BRANCH_COUNT + 1) if b != OPEN_BRANCH]
    return [OPEN_BRANCH, *restricted] if fleet.mumble_open else restricted


def acquire(fleet: EveFleet) -> VoiceChannelLease | None:
    """Lease a free branch for the fleet (``branch_order``). None when the
    branches it may use are taken."""
    existing = VoiceChannelLease.active().filter(fleet=fleet).first()
    if existing:
        return existing
    taken = set(VoiceChannelLease.active().values_list("branch", flat=True))
    for branch in branch_order(fleet):
        if branch in taken:
            continue
        try:
            with transaction.atomic():
                lease = VoiceChannelLease.objects.create(
                    branch=branch, fleet=fleet
                )
        except IntegrityError:
            continue
        VoiceAuditEvent.record(
            VoiceAuditEvent.KIND_LEASE, fleet_id=fleet.id, branch=branch
        )
        return lease
    logger.warning("No free voice branch for fleet %s", fleet.id)
    return None


def release(lease: VoiceChannelLease, reason: str, now=None) -> set[int]:
    """End a lease and its fleet's grants. Returns the affected characters."""
    now = now or timezone.now()
    lease.released_at = now
    lease.save(update_fields=["released_at"])
    grants = VoiceGrant.objects.filter(fleet_id=lease.fleet_id).exclude(
        expires_at__lte=now
    )
    affected = set(grants.values_list("character_id", flat=True))
    grants.update(expires_at=now)
    VoiceAuditEvent.record(
        VoiceAuditEvent.KIND_RELEASE,
        fleet_id=lease.fleet_id,
        branch=lease.branch,
        reason=reason,
    )
    return affected


def schedule_release(fleet: EveFleet, now=None) -> None:
    """The fleet closed: keep its branch for 30 more minutes."""
    now = now or timezone.now()
    VoiceChannelLease.active().filter(
        fleet=fleet, release_after__isnull=True
    ).update(release_after=now + AFTER_CLOSE)


def candidate_fleets(now=None):
    """Mumble fleets that could want a branch around now."""
    now = now or timezone.now()
    return EveFleet.objects.filter(
        voice_option__kind=FleetVoiceOption.KIND_MUMBLE,
        start_time__lte=now + EARLY_LEASE,
        start_time__gte=now - timedelta(days=1),
    ).exclude(status__in=INACTIVE_STATUSES)


def maintain(now=None) -> dict:
    """Release leases that should end, then lease branches for fleets that
    want one. Returns {"released": [...], "acquired": [...], "affected": set}.
    """
    now = now or timezone.now()
    released, acquired, affected = [], [], set()
    for lease in VoiceChannelLease.active().select_related(
        "fleet__voice_option"
    ):
        reason = release_reason(lease, now)
        if reason:
            affected |= release(lease, reason, now)
            released.append(lease.fleet_id)
    leased = set(VoiceChannelLease.active().values_list("fleet_id", flat=True))
    for fleet in candidate_fleets(now).order_by("start_time"):
        if fleet.id in leased or not wants_lease(fleet, now):
            continue
        if acquire(fleet):
            acquired.append(fleet.id)
    return {"released": released, "acquired": acquired, "affected": affected}
