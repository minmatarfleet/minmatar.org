"""Which prime time an hour of play falls in.

Uses the codes a pilot picks on their profile (EvePlayer.prime_choices).
The fleets page buckets a fleet's start hour here (the fleet's time region),
and campaign stats store a pilot's busiest hour with it. AP_EU is a code
pilots can declare, but no observed hour maps to it.

A pilot's own timezone is not this: read it from the timezones app
(timezones.services, see docs/timezones.md).
"""

from __future__ import annotations

UNKNOWN_BUCKET = "??"

# The UTC hours in each bucket. US wraps past midnight.
PRIME_BUCKET_HOURS = (
    ("US", (22, 23, 0, 1, 2, 3, 4)),
    ("US_AP", (5, 6, 7, 8, 9)),
    ("AP", (10, 11, 12, 13, 14)),
    ("EU", (15, 16, 17, 18, 19)),
    ("EU_US", (20, 21)),
)
_BUCKET_BY_HOUR = {
    hour: code for code, hours in PRIME_BUCKET_HOURS for hour in hours
}


def prime_bucket(hour_utc: int) -> str:
    """The prime-time code for an hour in UTC (EVE time)."""
    return _BUCKET_BY_HOUR.get(hour_utc, UNKNOWN_BUCKET)
