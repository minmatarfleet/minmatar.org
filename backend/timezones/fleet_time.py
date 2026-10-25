"""Which timezones play at a fleet's start time.

A fleet's timezones are the brackets whose window (on that region's own
clock) holds the start. A start in nobody's evening gets the nearest
bracket instead. See docs/timezones.md.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from timezones.brackets import (
    BRACKET_CODES,
    BRACKETS,
    LATE_HOURS,
    PRIME_HOURS,
    REFERENCE_ZONES,
    window_kind,
)

# Invite pickers send this to mean "don't filter by timezone".
ANY = "any"


def brackets_at(when: datetime) -> list[str]:
    """Bracket codes whose window holds ``when`` (an aware datetime)."""
    out = []
    for bracket in BRACKETS:
        hour = when.astimezone(REFERENCE_ZONES[bracket.region]).hour
        if window_kind(hour) == bracket.kind:
            out.append(bracket.code)
    return out


def _hours_to_window(when: datetime, bracket) -> float:
    """Hours from ``when`` to the nearest edge of the bracket's window."""
    hours = PRIME_HOURS if bracket.kind == "prime" else LATE_HOURS
    local = when.astimezone(REFERENCE_ZONES[bracket.region])
    best = 24.0
    for step in range(-12, 13):
        moment = local + timedelta(hours=step)
        if moment.hour in hours:
            best = min(best, abs(step))
    return best


def fleet_timezones(start: datetime) -> tuple[list[str], bool]:
    """The fleet's brackets, and whether they are only the nearest one.

    Only base (evening) brackets are offered as the nearest, never a late
    one, since late windows are small and mostly overlap another evening.
    """
    held = brackets_at(start)
    if held:
        return held, False
    evenings = [b for b in BRACKETS if b.kind == "prime"]
    nearest = min(evenings, key=lambda b: _hours_to_window(start, b))
    return [nearest.code], True


def in_timezones(brackets, codes) -> bool:
    """Does a pilot with ``brackets`` play in any of ``codes``? Pilots with
    no brackets yet always do: nothing says they don't."""
    if not brackets:
        return True
    return bool(set(brackets) & set(codes))


def clean_codes(codes) -> list[str]:
    """Known bracket codes, in bracket order."""
    wanted = set(codes or ())
    return [code for code in BRACKET_CODES if code in wanted]
