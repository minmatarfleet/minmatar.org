"""Removing a fleet without losing its history.

A fleet that ran has attendance (``EveFleetInstance`` and its members, which
trial approval, alliance health, corp stats and campaigns read) and may have
SRP claims. Deleting it would cascade all of that away, so such a fleet is
cancelled instead: it leaves the schedule and the FC stats, and keeps its
records. Only a fleet that never started is really deleted.
"""

from django.utils import timezone

from fleets.models import EveFleet, EveFleetInstance

DELETED = "deleted"
CANCELLED = "cancelled"


def fleet_has_history(fleet: EveFleet) -> bool:
    """True once a fleet has tracked attendance or any SRP claim."""
    return (
        EveFleetInstance.objects.filter(eve_fleet=fleet).exists()
        or fleet.reimbursements.exists()
    )


def remove_fleet(fleet: EveFleet) -> str:
    """Delete a fleet that never ran; cancel one that did.

    Returns ``DELETED`` or ``CANCELLED`` so callers can say which happened.
    """
    if not fleet_has_history(fleet):
        fleet.delete()
        return DELETED

    EveFleetInstance.objects.filter(
        eve_fleet=fleet, end_time__isnull=True
    ).update(end_time=timezone.now())
    fleet.status = "cancelled"
    # A full save, so the schedule signal drops it like any other cancel.
    fleet.save()
    return CANCELLED
