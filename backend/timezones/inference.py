"""Which timezone roles a pilot's activity earns. Pure functions, no queries.

A pilot gets:

1. the base role of their home timezone: where their evening after work is,
   from a model of when US and EU pilots play, or from their declared prime
   time until there is enough activity to judge;
2. the + role of their home timezone when they are regularly on late;
3. the base role of any other timezone whose evening they regularly play in.

"Regularly" counts distinct evenings, not events, so one long fight is one
evening. Time inside a pilot's own evening never counts toward another
timezone: an EU pilot on at 01:00 UTC is up late, not playing US prime.

The research behind the numbers is in docs/timezones.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable

from timezones.brackets import (
    AU,
    EU,
    LATE,
    PRIME,
    REFERENCE_ZONES,
    REGIONS,
    US,
    bracket_for,
    window_kind,
)

# Days of activity a pilot is judged on.
WINDOW_DAYS = 90

# A role is added at ADD_*, and kept until the pilot falls below KEEP_*, so
# a pilot near the line does not gain and lose it every run.
ADD_MIN_EVENINGS = 4
ADD_MIN_SHARE = 0.15
KEEP_MIN_EVENINGS = 2
KEEP_MIN_SHARE = 0.08

# The home model must be this sure before activity overrides what the pilot
# declared. Below it, the declared prime time wins.
CONFIDENT = 0.8
# How much a declared prime time tilts the home model.
DECLARED_PRIOR = 0.7
# Events are not independent (one fight is many killmails), so the
# likelihood is tempered and grows with the square root of the event count.
TEMPER = 0.5

# What a declared EvePlayer.prime_time says about where a pilot lives. The
# crossover codes come from the application form's region + time of day
# answer, so they mean the opposite of their labels: EU_US ("EUTZ - USTZ")
# is US pilots who play afternoons, US_AP is EU pilots who play mornings.
DECLARED_REGION = {
    "US": US,
    "EU": EU,
    "AP": AU,
    "EU_US": US,
    "US_AP": EU,
    "AP_EU": EU,
}

# Share of play per hour on each region's own clock (index 0 = 00:00), for
# pilots whose application recorded their browser timezone: 100 US and 82
# EU pilots, July-October 2026. Re-derive with
# `manage.py check_timezones`.
HOME_PROFILES = {
    US: (
        0.0417, 0.0243, 0.0152, 0.0168, 0.0078, 0.0053,
        0.0140, 0.0057, 0.0079, 0.0145, 0.0260, 0.0306,
        0.0382, 0.0667, 0.0854, 0.0678, 0.0534, 0.0496,
        0.0469, 0.1070, 0.0934, 0.0734, 0.0508, 0.0576,
    ),
    EU: (
        0.0417, 0.0451, 0.0409, 0.0173, 0.0077, 0.0060,
        0.0077, 0.0080, 0.0077, 0.0173, 0.0150, 0.0168,
        0.0268, 0.0322, 0.0319, 0.0306, 0.0467, 0.0453,
        0.0399, 0.0787, 0.1110, 0.1187, 0.1351, 0.0717,
    ),
}  # fmt: skip

ACTIVITY = "activity"
DECLARED = "declared"


@dataclass(frozen=True)
class Assessment:
    home: str | None
    home_source: str | None  # ACTIVITY, DECLARED or None
    brackets: frozenset[str]
    declared_home: str | None = None
    inferred_home: str | None = None
    inferred_confidence: float | None = None  # the home model's P, if it ran
    # "<region>_<prime|late>" -> distinct evenings, as counted for roles
    evenings: dict[str, int] = field(default_factory=dict)
    active_days: int = 0
    events: int = 0


def evening_of(local: datetime):
    """The evening a moment belongs to: 01:00 is the night before."""
    return (local - timedelta(hours=6)).date()


def count_evenings(
    events: Iterable[datetime], home: str | None = None
) -> dict[str, int]:
    """Distinct evenings with activity in each region's prime and late.

    With ``home`` set, events inside the home region's own prime or late
    window are left out of every other region's counts.
    """
    seen: dict[str, set] = {}
    for event in events:
        home_kind = None
        if home is not None:
            home_kind = window_kind(
                event.astimezone(REFERENCE_ZONES[home]).hour
            )
        for region in REGIONS:
            if home is not None and region != home and home_kind is not None:
                continue
            local = event.astimezone(REFERENCE_ZONES[region])
            kind = window_kind(local.hour)
            if kind is None:
                continue
            seen.setdefault(f"{region}_{kind}", set()).add(evening_of(local))
    return {key: len(days) for key, days in seen.items()}


def home_probabilities(
    events: list[datetime], declared: str | None = None
) -> dict[str, float]:
    """P(US) and P(EU) from when the pilot plays, tilted by what they declared.

    AU is not modelled: too few known AU pilots to learn their week from.
    """
    count = len(events)
    if not count:
        return {}
    declared_region = DECLARED_REGION.get(declared or "")
    scale = TEMPER / max(1.0, math.sqrt(count) / 2)
    log_p = {}
    for region in (US, EU):
        zone = REFERENCE_ZONES[region]
        profile = HOME_PROFILES[region]
        likelihood = sum(
            math.log(profile[event.astimezone(zone).hour]) for event in events
        )
        prior = 0.5
        if declared_region in (US, EU):
            prior = (
                DECLARED_PRIOR
                if declared_region == region
                else 1 - DECLARED_PRIOR
            )
        log_p[region] = likelihood * scale + math.log(prior)
    top = max(log_p.values())
    total = sum(math.exp(value - top) for value in log_p.values())
    return {
        region: math.exp(value - top) / total
        for region, value in log_p.items()
    }


def infer_home(events: list[datetime], declared: str | None = None):
    """(region, P(region)) from activity; P is None for AU, (None, None)
    without activity."""
    if not events:
        return None, None
    raw = count_evenings(events)
    au_prime = raw.get(f"{AU}_{PRIME}", 0)
    if au_prime > max(
        raw.get(f"{US}_{PRIME}", 0), raw.get(f"{EU}_{PRIME}", 0)
    ):
        return AU, None
    probabilities = home_probabilities(events, declared)
    best = max(probabilities, key=probabilities.get)
    return best, probabilities[best]


def _regular(evenings: int, active_days: int, holding: bool) -> bool:
    min_evenings = KEEP_MIN_EVENINGS if holding else ADD_MIN_EVENINGS
    min_share = KEEP_MIN_SHARE if holding else ADD_MIN_SHARE
    return evenings >= min_evenings and evenings >= min_share * active_days


def assess(
    events: Iterable[datetime],
    declared: str | None = None,
    held: Iterable[str] = (),
) -> Assessment:
    """The roles a pilot earns from ``events`` (aware datetimes).

    ``held`` is the roles they hold now, which only need the lower KEEP_*
    bar to stay.
    """
    events = sorted(events)
    held = set(held)
    declared_home = DECLARED_REGION.get(declared or "")
    inferred, confidence = infer_home(events, declared)
    if inferred and (
        confidence is None or confidence >= CONFIDENT or not declared_home
    ):
        home, source = inferred, ACTIVITY
    elif declared_home:
        home, source = declared_home, DECLARED
    else:
        home, source = None, None
    if home is None:
        return Assessment(None, None, frozenset(), events=len(events))

    evenings = count_evenings(events, home)
    active_days = len({event.date() for event in events})
    roles = {bracket_for(home, PRIME).code}

    late = bracket_for(home, LATE).code
    if _regular(evenings.get(f"{home}_{LATE}", 0), active_days, late in held):
        roles.add(late)

    for region in REGIONS:
        if region == home:
            continue
        code = bracket_for(region, PRIME).code
        if _regular(
            evenings.get(f"{region}_{PRIME}", 0), active_days, code in held
        ):
            roles.add(code)

    return Assessment(
        home=home,
        home_source=source,
        brackets=frozenset(roles),
        declared_home=declared_home,
        inferred_home=inferred,
        inferred_confidence=confidence,
        evenings=evenings,
        active_days=active_days,
        events=len(events),
    )
