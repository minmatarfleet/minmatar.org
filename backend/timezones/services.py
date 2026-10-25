"""Pilot timezones: read them here, and only this module writes them.

Readers:

- ``timezone_for(user_id)`` / ``timezones_for(user_ids)``: the stored
  PilotTimezone (home, brackets, and the declared and inferred inputs)
- ``users_in_bracket(code)``: everyone who holds a bracket
- ``timezone_tags_for(user_ids)``: what pages show (timezones.schemas)
- ``brackets_for(user_ids)`` / ``home_counts()``: rollups

Hook into changes with the ``pilot_timezone_changed`` signal. It fires
after a pilot's home, brackets or eligibility change, with the instance and
the previous values. Discord role sync (timezones.discord_roles) is one
receiver.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Iterable

from django.contrib.auth.models import User
from django.dispatch import Signal
from django.utils import timezone

from discord.models import DiscordUser
from eveonline.models import EvePlayer
from groups.models import UserCommunityStatus
from timezones.activity import load_events
from timezones.inference import WINDOW_DAYS, Assessment, assess
from timezones.models import PilotTimezone
from timezones.schemas import TimezoneTag

logger = logging.getLogger(__name__)

# kwargs: instance, previous_home, previous_brackets, previous_eligible
pilot_timezone_changed = Signal()

ELIGIBLE_STATUSES = (
    UserCommunityStatus.STATUS_ACTIVE,
    UserCommunityStatus.STATUS_TRIAL,
)


def timezone_for(user_id: int) -> PilotTimezone | None:
    return PilotTimezone.objects.filter(user_id=user_id).first()


def timezones_for(
    user_ids: Iterable[int], using: str = "default"
) -> dict[int, PilotTimezone]:
    ids = {int(uid) for uid in user_ids if uid}
    return {
        row.user_id: row
        for row in PilotTimezone.objects.using(using).filter(user_id__in=ids)
    }


def timezone_tag(row: PilotTimezone | None) -> TimezoneTag:
    if row is None or not row.brackets:
        return TimezoneTag()
    return TimezoneTag(brackets=list(row.brackets), source=row.home_source)


def timezone_tags_for(
    user_ids: Iterable[int], using: str = "default"
) -> dict[int, TimezoneTag]:
    """Every asked user's tag; users never assessed get an empty one."""
    ids = {int(uid) for uid in user_ids if uid}
    rows = timezones_for(ids, using=using)
    return {uid: timezone_tag(rows.get(uid)) for uid in ids}


def home_counts(eligible_only: bool = True) -> dict[str, int]:
    """Region (US, EU, AU) -> how many pilots call it home."""
    rows = PilotTimezone.objects.exclude(home__isnull=True).exclude(home="")
    if eligible_only:
        rows = rows.filter(eligible=True)
    counts: dict[str, int] = {}
    for home in rows.values_list("home", flat=True):
        counts[home] = counts.get(home, 0) + 1
    return counts


def brackets_for(user_ids: Iterable[int]) -> dict[int, list[str]]:
    """user id -> bracket codes, for users who have any."""
    return {
        user_id: list(brackets)
        for user_id, brackets in PilotTimezone.objects.filter(
            user_id__in={int(uid) for uid in user_ids if uid}
        ).values_list("user_id", "brackets")
        if brackets
    }


def users_in_bracket(code: str, eligible_only: bool = True):
    """Users whose brackets include ``code`` (JSON contains is not portable
    to every backend, so filter in Python over the indexed eligible rows)."""
    rows = PilotTimezone.objects.all()
    if eligible_only:
        rows = rows.filter(eligible=True)
    ids = [
        user_id
        for user_id, brackets in rows.values_list("user_id", "brackets")
        if code in (brackets or [])
    ]
    return User.objects.filter(id__in=ids)


def eligible_user_ids(user_ids: Iterable[int] | None = None) -> set[int]:
    """Active or trial members with Discord linked."""
    statuses = UserCommunityStatus.objects.filter(status__in=ELIGIBLE_STATUSES)
    if user_ids is not None:
        statuses = statuses.filter(user_id__in=list(user_ids))
    ids = set(statuses.values_list("user_id", flat=True))
    return set(
        DiscordUser.objects.filter(user_id__in=ids).values_list(
            "user_id", flat=True
        )
    )


def population() -> set[int]:
    """Everyone worth assessing: community members (on leave included, so
    their timezone is known when they come back) and anyone already
    assessed, so leavers are re-marked ineligible."""
    return set(
        UserCommunityStatus.objects.values_list("user_id", flat=True)
    ) | set(PilotTimezone.objects.values_list("user_id", flat=True))


def assess_users(
    user_ids: Iterable[int] | None = None,
    now: datetime | None = None,
    save: bool = True,
) -> dict[int, Assessment]:
    """Assess pilots and store the result. Returns user id -> Assessment."""
    now = now or timezone.now()
    ids = set(population() if user_ids is None else user_ids)
    ids &= set(User.objects.filter(id__in=ids).values_list("id", flat=True))
    if not ids:
        return {}
    events = load_events(ids, now - timedelta(days=WINDOW_DAYS))
    declared = dict(
        EvePlayer.objects.filter(user_id__in=ids).values_list(
            "user_id", "prime_time"
        )
    )
    eligible = eligible_user_ids(ids)
    existing = timezones_for(ids)
    results = {}
    for user_id in sorted(ids):
        row = existing.get(user_id)
        result = assess(
            events.get(user_id, ()),
            declared.get(user_id),
            held=row.brackets if row else (),
        )
        results[user_id] = result
        if save:
            _store(
                user_id,
                row,
                result,
                declared.get(user_id),
                user_id in eligible,
                now,
            )
    return results


def _store(user_id, row, result, declared, eligible, now) -> PilotTimezone:
    brackets = sorted(result.brackets)
    previous = (
        (row.home, list(row.brackets), row.eligible)
        if row
        else (None, [], False)
    )
    changed = previous != (result.home, brackets, eligible)
    if row is None:
        row = PilotTimezone(user_id=user_id, changed_at=now)
    row.declared_prime_time = declared
    row.declared_home = result.declared_home
    row.inferred_home = result.inferred_home
    row.inferred_confidence = result.inferred_confidence
    row.home = result.home
    row.home_source = result.home_source
    row.brackets = brackets
    row.evenings = result.evenings
    row.active_days = result.active_days
    row.events = result.events
    row.eligible = eligible
    row.assessed_at = now
    if changed:
        row.changed_at = now
    row.save()
    if changed:
        for receiver, response in pilot_timezone_changed.send_robust(
            sender=PilotTimezone,
            instance=row,
            previous_home=previous[0],
            previous_brackets=previous[1],
            previous_eligible=previous[2],
        ):
            if isinstance(response, Exception):
                logger.error(
                    "pilot_timezone_changed receiver %s failed for user %s: %s",
                    receiver,
                    user_id,
                    response,
                )
    return row
