"""Accepting an applicant with active can't-rejoin flags (design 06)."""

from dataclasses import asdict

from django.utils import timezone

from exits.helpers.history import active_flags_for, history_for
from exits.models import FlagAcceptance


def flags_blocking(application) -> list:
    return active_flags_for(application.user, [])


def flagged_response(application) -> dict:
    """The 409 body: the flagged history entries, for the confirm dialog."""
    flagged = [e for e in history_for(application.user, []) if e.flag_active]
    return {
        "detail": "This pilot is marked can't rejoin. Confirm to accept anyway.",
        "flags": [asdict(entry) for entry in flagged],
    }


def record_acceptance(application, flags, by) -> FlagAcceptance:
    return FlagAcceptance.objects.create(
        application=application,
        flag_ids=[flag.pk for flag in flags],
        accepted_by=by,
        accepted_at=timezone.now(),
    )
