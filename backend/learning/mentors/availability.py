"""When a pilot and a mentor are both around.

Each side has timezone brackets for weekday evenings and for weekend
evenings (codes from timezones.brackets) and the evenings they play
(0 = Monday ... 6 = Sunday). An evening belongs to the day it starts on, on
the bracket's own clock: 01:00 Saturday Eastern is still Friday evening.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone

from timezones.brackets import (
    BRACKETS_BY_CODE,
    REFERENCE_ZONES,
    window_kind,
)

WEEKEND_DAYS = (5, 6)
ALL_DAYS = tuple(range(7))
SLOT_HORIZON_DAYS = 14
SLOT_LEAD_HOURS = 12


@dataclass(frozen=True)
class Availability:
    weekday_brackets: tuple[str, ...]
    weekend_brackets: tuple[str, ...]
    days: tuple[int, ...]

    @classmethod
    def build(cls, weekday, weekend, days) -> "Availability":
        return cls(
            weekday_brackets=clean_brackets(weekday),
            weekend_brackets=clean_brackets(weekend),
            days=clean_days(days),
        )


def clean_brackets(codes) -> tuple[str, ...]:
    return tuple(
        code for code in dict.fromkeys(codes or []) if code in BRACKETS_BY_CODE
    )


def clean_days(days) -> tuple[int, ...]:
    out = []
    for day in days or []:
        try:
            value = int(day)
        except (TypeError, ValueError):
            continue
        if 0 <= value <= 6 and value not in out:
            out.append(value)
    return tuple(sorted(out))


def evening_weekday(code: str, moment: datetime) -> int | None:
    """The weekday whose evening `moment` falls in, for one bracket."""
    bracket = BRACKETS_BY_CODE[code]
    local = moment.astimezone(REFERENCE_ZONES[bracket.region])
    if window_kind(local.hour) != bracket.kind:
        return None
    evening = local if local.hour >= 12 else local - timedelta(days=1)
    return evening.weekday()


def is_available(person: Availability, moment: datetime) -> bool:
    for code in person.weekday_brackets:
        day = evening_weekday(code, moment)
        if day is not None and day not in WEEKEND_DAYS and day in person.days:
            return True
    for code in person.weekend_brackets:
        day = evening_weekday(code, moment)
        if day is not None and day in WEEKEND_DAYS and day in person.days:
            return True
    return False


def _hours(start: datetime, days: int):
    moment = start.replace(minute=0, second=0, microsecond=0) + timedelta(
        hours=1
    )
    end = start + timedelta(days=days)
    while moment < end:
        yield moment
        moment += timedelta(hours=1)


def shared_hours(
    a: Availability, b: Availability, now: datetime | None = None
) -> list[datetime]:
    """Every hour in the next two weeks when both are around."""
    now = now or datetime.now(dt_timezone.utc)
    return [
        moment
        for moment in _hours(now, SLOT_HORIZON_DAYS)
        if is_available(a, moment) and is_available(b, moment)
    ]


def fit(pilot: Availability, mentor: Availability, now=None) -> str:
    """How the mentor's times sit against the pilot's, for the card tag.

    "evenings" (weekday and weekend overlap), "weekdays", "weekends" or
    "none".
    """
    weekday = bool(
        shared_hours(
            Availability(pilot.weekday_brackets, (), pilot.days), mentor, now
        )
    )
    weekend = bool(
        shared_hours(
            Availability((), pilot.weekend_brackets, pilot.days), mentor, now
        )
    )
    if weekday and weekend:
        return "evenings"
    if weekday:
        return "weekdays"
    if weekend:
        return "weekends"
    return "none"


def suggested_slots(
    pilot: Availability,
    mentor: Availability,
    now: datetime | None = None,
    limit: int = 3,
) -> list[datetime]:
    """The first shared hour of each shared evening, soonest first."""
    now = now or datetime.now(dt_timezone.utc)
    earliest = now + timedelta(hours=SLOT_LEAD_HOURS)
    slots: list[datetime] = []
    previous: datetime | None = None
    for moment in shared_hours(pilot, mentor, now):
        starts_block = previous is None or moment - previous > timedelta(
            hours=1
        )
        previous = moment
        if starts_block and moment >= earliest:
            slots.append(moment)
            if len(slots) >= limit:
                break
    return slots
