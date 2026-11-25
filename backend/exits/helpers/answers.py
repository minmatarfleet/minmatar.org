"""The CEO's answers on the Departures tab (design 04 and 06)."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from eveonline.helpers.corporations.permissions import user_is_ceo
from eveonline.models import EveCorporation
from exits.models import (
    KIND_ALLIANCE_MOVE,
    KIND_EXIT,
    REASON_KICKED_INACTIVE,
    REASON_KICKED_OTHER,
    REASON_LEFT,
    STATUS_CONFIRMED,
    Departure,
    RejoinFlag,
)

REASONS = (REASON_KICKED_INACTIVE, REASON_KICKED_OTHER, REASON_LEFT)
KICKS = (REASON_KICKED_INACTIVE, REASON_KICKED_OTHER)
UNDO_WINDOW = timedelta(hours=1)


class AnswerError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def can_answer(user: User, corporation: EveCorporation) -> bool:
    return bool(user and (user.is_superuser or user_is_ceo(user, corporation)))


def _locked_ids(departure_ids) -> set[int]:
    """Departures whose survey has gone out: their reason can't change."""
    # Imported here: surveys depends on exits, not the other way round.
    from surveys.models import (  # pylint: disable=import-outside-toplevel
        ExitSurveyInvite,
    )

    return set(
        ExitSurveyInvite.objects.filter(
            departure_id__in=departure_ids
        ).values_list("departure_id", flat=True)
    )


def _validate(reason, can_rejoin, note):
    if reason not in REASONS:
        raise AnswerError("Pick a reason")
    if reason in KICKS and can_rejoin is None:
        raise AnswerError("Say whether they can rejoin")
    if reason in KICKS and can_rejoin is False and not note.strip():
        raise AnswerError("A note is required for a pilot who can't rejoin")


def _alert_open_applications(departure: Departure) -> None:
    """A new flag alerts recruiters of the pilot's pending applications."""
    # Imported here: exits.tasks imports the helpers that import this module.
    from exits.helpers.alerts import (  # pylint: disable=import-outside-toplevel
        open_applications_for,
    )
    from exits.tasks import (  # pylint: disable=import-outside-toplevel
        alert_application,
    )

    for application_id in open_applications_for(
        departure.user, [departure.character_id]
    ):
        transaction.on_commit(
            lambda pk=application_id: alert_application.delay(pk)
        )


def _sync_flag(departure: Departure, by: User, now) -> None:
    active = departure.flags.filter(cleared_at__isnull=True).first()
    if departure.can_rejoin is False:
        if active:
            if active.note != departure.note:
                active.note = departure.note
                active.save(update_fields=["note"])
            return
        RejoinFlag.objects.create(
            character_id=departure.character_id,
            user=departure.user,
            departure=departure,
            corporation=departure.corporation,
            note=departure.note,
            set_by=by,
            set_at=now,
        )
        _alert_open_applications(departure)
    elif active:
        active.cleared_by = by
        active.cleared_at = now
        active.save(update_fields=["cleared_by", "cleared_at"])


@transaction.atomic
def answer(
    by: User,
    corporation: EveCorporation,
    departure_ids: list[int],
    *,
    reason: str,
    can_rejoin: bool | None,
    note: str,
) -> list[Departure]:
    if not can_answer(by, corporation):
        raise AnswerError("Only the corporation's CEO can answer", 403)
    note = (note or "").strip()
    _validate(reason, can_rejoin, note)
    if reason == REASON_LEFT:
        can_rejoin = None

    ids = set(departure_ids)
    departures = list(
        Departure.objects.select_for_update()
        .select_related("corporation")
        .filter(pk__in=ids, corporation=corporation, status=STATUS_CONFIRMED)
    )
    if not ids or len(departures) != len(ids):
        raise AnswerError(
            "Some of these departures aren't this corporation's", 404
        )

    locked = _locked_ids(ids)
    now = timezone.now()
    for departure in departures:
        if departure.pk in locked and departure.reason != reason:
            raise AnswerError(
                "The survey has been sent, so the reason can't change", 409
            )
        departure.reason = reason
        departure.can_rejoin = can_rejoin
        departure.note = note
        departure.answered_by = by
        departure.answered_at = now
        if departure.pk not in locked:
            departure.survey_due_at = (
                now + UNDO_WINDOW
                if reason == REASON_LEFT
                and departure.kind in (KIND_EXIT, KIND_ALLIANCE_MOVE)
                else None
            )
        departure.save()
        _sync_flag(departure, by, now)
    return departures


def can_clear(user: User, flag: RejoinFlag) -> bool:
    return can_answer(user, flag.corporation)


@transaction.atomic
def clear_flag(by: User, flag: RejoinFlag) -> RejoinFlag:
    if not can_clear(by, flag):
        raise AnswerError(
            "Only the CEO of the corporation that set it can clear it", 403
        )
    if flag.cleared_at is None:
        flag.cleared_by = by
        flag.cleared_at = timezone.now()
        flag.save(update_fields=["cleared_by", "cleared_at"])
    return flag
