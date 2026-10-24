"""EVE time: the UTC clock the game, and every EVE-facing page, runs on.

One place to answer "which EVE month or day is this?". Windows are
half-open: ``start <= t < end``.

Two other calendars are deliberately separate:

* The campaign calendar (days roll over at 11:00 UTC, weeks open on
  Thursday) lives in ``campaigns.helpers``.
* Tribe activity reports keep an inclusive period end (23:59:59.999999)
  in ``tribes.reports.queries.common.period_window``.
"""

from __future__ import annotations

from datetime import date, datetime
from datetime import timezone as dt_timezone

from django.utils import timezone

EVE_TZ = dt_timezone.utc


def eve_now() -> datetime:
    """The current moment in EVE time."""
    return timezone.now().astimezone(EVE_TZ)


def as_eve_time(value: datetime) -> datetime:
    """An aware datetime in EVE time.

    Naive input is read in the project time zone (``TIME_ZONE``, UTC).
    """
    aware = timezone.make_aware(value) if timezone.is_naive(value) else value
    return aware.astimezone(EVE_TZ)


def month_key(value: date | datetime) -> str:
    """``YYYY-MM`` of the EVE month ``value`` falls in."""
    if isinstance(value, datetime):
        value = as_eve_time(value)
    return f"{value.year:04d}-{value.month:02d}"


def month_bounds(
    value: date | datetime | None = None,
) -> tuple[datetime, datetime]:
    """Half-open EVE calendar month containing ``value`` (default: now)."""
    if value is None:
        value = eve_now()
    elif isinstance(value, datetime):
        value = as_eve_time(value)
    start = datetime(value.year, value.month, 1, tzinfo=EVE_TZ)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end
