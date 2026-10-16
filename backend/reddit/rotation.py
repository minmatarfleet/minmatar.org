"""Which corporation gets each slot of the alliance Reddit rotation.

Pure functions with no database: `reddit.schedule` feeds them and saves the
result.

One alliance post every SLOT_DAYS days, counted from EPOCH, at a time spread
between downtime and the US evening. Each month's slots are shared out by
weight (high priority counts double), carrying over whatever a corporation
was owed or got extra in the months before. No corporation posts twice
within COOLDOWN.

A draft is repaired rather than rebuilt when something changes: assignments
that are still valid stay put, so one change moves a slot or two instead of
reshuffling the month.
"""

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone as dt_timezone

# Bump when the rules change, so stored drafts are worked out again.
VERSION = 1

EPOCH = date(2026, 10, 1)
SLOT_DAYS = 2
COOLDOWN = timedelta(days=7)
WEIGHTS = {"high": 2, "normal": 1}
# Owed or extra slots carried into a month, at most.
CARRY_LIMIT = 1.5

ANY, EU, US = "any", "eu", "us"
# (start, length) in EVE time. Downtime ends 11:00; 02:00 is 22:00 US East.
WINDOWS = {
    ANY: (time(11, 30), timedelta(hours=14, minutes=30)),
    EU: (time(11, 30), timedelta(hours=9, minutes=30)),
    US: (time(18, 0), timedelta(hours=8)),
}


@dataclass(frozen=True)
class Member:
    """A template in the rotation."""

    id: int
    weight: int
    window: str = ANY


def month_start(day: date) -> date:
    return day.replace(day=1)


def next_month(month: date) -> date:
    return (month.replace(day=28) + timedelta(days=4)).replace(day=1)


def previous_month(month: date) -> date:
    return (month.replace(day=1) - timedelta(days=1)).replace(day=1)


def slot_dates(month: date) -> list[date]:
    """Every slot date in the month."""
    first = month + timedelta(days=-(month - EPOCH).days % SLOT_DAYS)
    end = next_month(month)
    days = []
    while first < end:
        days.append(first)
        first += timedelta(days=SLOT_DAYS)
    return days


def slot_time(day: date, window: str = ANY) -> datetime:
    """When a slot goes out: a fixed point in the window picked from the
    date, so it is the same every time it is worked out."""
    start, length = WINDOWS.get(window, WINDOWS[ANY])
    digest = hashlib.sha256(day.isoformat().encode()).digest()
    fraction = int.from_bytes(digest[:4], "big") / 2**32
    minutes = int(length.total_seconds() // 60 * fraction)
    minutes -= minutes % 5
    return datetime.combine(day, start, tzinfo=dt_timezone.utc) + timedelta(
        minutes=minutes
    )


def max_posts(slots: int) -> int:
    """The most one corporation can get in this many slots without posting
    twice within the cooldown."""
    # Slots this far apart always clear the cooldown, whatever the jitter.
    spacing = math.ceil(COOLDOWN / timedelta(days=SLOT_DAYS))
    return math.ceil(slots / spacing)


def quotas(
    members: list[Member], slots: int, carry: dict[int, float]
) -> dict[int, int]:
    """How many of the month's slots each member gets: its weighted share
    plus what it is owed, rounded so the counts add up to the slots (largest
    remainder first, ties by id)."""
    if not members:
        return {}
    total = sum(m.weight for m in members)
    cap = max_posts(slots)
    want = {
        m.id: max(0.0, slots * m.weight / total + _clamp(carry.get(m.id, 0)))
        for m in members
    }
    given = {i: min(cap, math.floor(w)) for i, w in want.items()}
    left = slots - sum(given.values())
    order = sorted(
        want, key=lambda i: (-(want[i] - math.floor(want[i])), -want[i], i)
    )
    while left > 0:
        room = [i for i in order if given[i] < cap]
        if not room:
            break
        for i in room[:left]:
            given[i] += 1
            left -= 1
    # Rounding can overshoot when carry pushes the shares past the slots.
    for i in sorted(given, key=lambda i: (want[i] - given[i], -i)):
        if left >= 0:
            break
        if given[i] > 0:
            given[i] -= 1
            left += 1
    return given


def _clamp(value: float) -> float:
    return max(-CARRY_LIMIT, min(CARRY_LIMIT, value))


def plan(
    days: list[date],
    members: list[Member],
    quota: dict[int, int],
    history: dict[int, list[datetime]],
    previous: dict[date, int] | None = None,
) -> dict[date, int]:
    """Assign members to slot dates; a date is left out only when every
    member is inside its cooldown.

    `history` holds each member's posts outside these days, for the
    cooldown. `previous` is the draft being repaired: each of its
    assignments is kept while the member is still in the rotation, still has
    quota left, and is clear of the cooldown. The gaps are filled by
    whoever is furthest behind an even spread of their quota.
    """
    by_id = {m.id: m for m in members}
    assigned: dict[date, int] = {}
    used: Counter = Counter()

    def clear(member: Member, day: date) -> bool:
        at = slot_time(day, member.window)
        times = list(history.get(member.id, []))
        times += [
            slot_time(d, member.window)
            for d, i in assigned.items()
            if i == member.id and d != day
        ]
        return all(abs(at - other) >= COOLDOWN for other in times)

    for day in days:
        member = by_id.get((previous or {}).get(day))
        if (
            member
            and used[member.id] < quota.get(member.id, 0)
            and clear(member, day)
        ):
            assigned[day] = member.id
            used[member.id] += 1

    for index, day in enumerate(days):
        if day in assigned:
            continue
        free = [m for m in members if clear(m, day)]
        if not free:
            continue
        # Nobody with quota left may be clear of the cooldown; then the slot
        # goes to whoever is closest to theirs, and fair share evens it up
        # next month.
        under = [m for m in free if used[m.id] < quota.get(m.id, 0)] or free
        progress = (index + 1) / len(days)
        pick = max(under, key=_behind(quota, used, progress))
        assigned[day] = pick.id
        used[pick.id] += 1
    return dict(sorted(assigned.items()))


def _behind(quota: dict[int, int], used: Counter, progress: float):
    """Sort key: how far a member is behind an even spread of its quota
    this far into the month, then how much quota it has left."""

    def key(m: Member):
        share = quota.get(m.id, 0)
        return (share * progress - used[m.id], share - used[m.id], -m.id)

    return key


def fingerprint(
    month: date,
    days: list[date],
    members: list[Member],
    carry: dict[int, float],
    history: dict[int, list[datetime]],
) -> str:
    """Everything a month's draft depends on. Same inputs, same draft."""
    first = slot_time(days[0]) if days else None
    recent = {
        str(i): sorted(
            t.isoformat()
            for t in times
            if first is None or t > first - COOLDOWN - timedelta(days=1)
        )
        for i, times in history.items()
    }
    payload = {
        "version": VERSION,
        "month": month.isoformat(),
        "days": [d.isoformat() for d in days],
        "members": sorted((m.id, m.weight, m.window) for m in members),
        "carry": {str(i): round(c, 4) for i, c in sorted(carry.items())},
        "history": {i: t for i, t in sorted(recent.items()) if t},
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()


def carry_from(
    months: list[tuple[dict[int, int], Counter]], member_ids: set[int]
) -> dict[int, float]:
    """What each member is owed (positive) or got extra (negative), from
    earlier months given as (weights, slots each got)."""
    carry = {i: 0.0 for i in member_ids}
    for weights, got in months:
        total = sum(weights.values())
        slots = sum(got.values())
        if not total or not slots:
            continue
        for i in member_ids:
            expected = slots * weights.get(i, 0) / total
            carry[i] += expected - got.get(i, 0)
    return {i: _clamp(c) for i, c in carry.items()}


def typical_interval_days(weight: int, total_weight: int) -> int | None:
    """Roughly how often a member with this weight posts."""
    if not weight or not total_weight:
        return None
    return round(SLOT_DAYS * total_weight / weight)
