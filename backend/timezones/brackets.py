"""The timezone brackets that become Discord roles.

Each region's brackets are fixed in that region's own clock, so daylight
saving moves them in EVE time but never in local time:

- the base role (USTZ, EUTZ, AUTZ) is the evening after work, 18:00-23:00
- the + role is the late side of that evening, 23:00-03:00

See docs/timezones.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo

US = "US"
EU = "EU"
AU = "AU"
REGIONS = (US, EU, AU)

# The clock each region's brackets are kept in.
REFERENCE_ZONES = {
    US: ZoneInfo("America/New_York"),
    EU: ZoneInfo("Europe/Berlin"),
    AU: ZoneInfo("Australia/Sydney"),
}

PRIME_HOURS = frozenset(range(18, 23))
LATE_HOURS = frozenset((23, 0, 1, 2))

PRIME = "prime"
LATE = "late"


@dataclass(frozen=True)
class Bracket:
    code: str  # the Discord role and auth group name
    region: str
    kind: str  # PRIME or LATE
    description: str


BRACKETS = (
    Bracket("USTZ", US, PRIME, "US evening, 18:00-23:00 Eastern"),
    Bracket("USTZ+", US, LATE, "US late night, 23:00-03:00 Eastern"),
    Bracket("EUTZ", EU, PRIME, "EU evening, 18:00-23:00 Central European"),
    Bracket("EUTZ+", EU, LATE, "EU late night, 23:00-03:00 Central European"),
    Bracket("AUTZ", AU, PRIME, "AU evening, 18:00-23:00 Sydney"),
    Bracket("AUTZ+", AU, LATE, "AU late night, 23:00-03:00 Sydney"),
)
BRACKETS_BY_CODE = {bracket.code: bracket for bracket in BRACKETS}
BRACKET_CODES = tuple(bracket.code for bracket in BRACKETS)


def bracket_for(region: str, kind: str) -> Bracket:
    for bracket in BRACKETS:
        if bracket.region == region and bracket.kind == kind:
            return bracket
    raise KeyError((region, kind))


def window_kind(local_hour: int) -> str | None:
    """PRIME, LATE or None for an hour on a region's own clock."""
    if local_hour in PRIME_HOURS:
        return PRIME
    if local_hour in LATE_HOURS:
        return LATE
    return None
