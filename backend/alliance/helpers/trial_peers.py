"""How a pilot compares with active alliance pilots, and how long trials run.

Built inside the hourly health snapshot (which already has every member's
30-day fleets, kills and voice) and read back by the Trial tab and the corp
Members row. Pilots see a tier, never the numbers behind it.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Optional

from groups.models import UserCommunityStatus, UserCommunityStatusHistory

SIGNALS = ("fleets", "kills", "voice")
# Upper percentile bound of each tier: Well below, Below average, Average,
# Above average, Well above.
TIER_BOUNDS = (20, 40, 60, 80)
TIER_KEYS = ("well_below", "below", "average", "above", "well_above")
TRIAL_LENGTH_DAYS = 365
# A corp average needs a few finished trials; fewer falls back to the
# alliance average.
MIN_TRIALS_FOR_AVERAGE = 3


def build_peers(
    *,
    active_user_ids: set[int],
    member_user_ids: set[int],
    fleets_30d: dict[int, int],
    kills_30d: dict[int, int],
    voice_hours_30d: dict[int, float],
) -> dict[str, Any]:
    """Sorted 30-day values of active pilots, plus each member's own.

    JSON keys are strings, so users are keyed by str(user_id).
    """

    def values(uid: int) -> list:
        return [
            int(fleets_30d.get(uid, 0)),
            int(kills_30d.get(uid, 0)),
            float(voice_hours_30d.get(uid, 0.0)),
        ]

    rows = {uid: values(uid) for uid in member_user_ids}
    active = [rows[uid] for uid in active_user_ids if uid in rows]
    return {
        "baseline": {
            signal: sorted(row[i] for row in active)
            for i, signal in enumerate(SIGNALS)
        },
        "users": {str(uid): row for uid, row in rows.items()},
    }


def build_trial_lengths(
    *, now: datetime, primary_corp: dict[int, int]
) -> dict[str, Any]:
    """Average days from trial to active over the last year, per corporation.

    Each trial → active change is measured from the user's latest move to
    trial before it. The corp is the user's main corp today.
    """
    since = now - timedelta(days=TRIAL_LENGTH_DAYS)
    history = defaultdict(list)
    for user_id, from_status, to_status, changed_at in (
        UserCommunityStatusHistory.objects.filter(
            to_status__in=[
                UserCommunityStatus.STATUS_TRIAL,
                UserCommunityStatus.STATUS_ACTIVE,
            ]
        )
        .order_by("changed_at")
        .values_list("user_id", "from_status", "to_status", "changed_at")
    ):
        history[user_id].append((from_status, to_status, changed_at))

    by_corp: dict[int, list[int]] = defaultdict(list)
    every: list[int] = []
    for user_id, changes in history.items():
        started = None
        for from_status, to_status, changed_at in changes:
            if to_status == UserCommunityStatus.STATUS_TRIAL:
                started = changed_at
                continue
            if (
                from_status != UserCommunityStatus.STATUS_TRIAL
                or started is None
                or changed_at < since
            ):
                continue
            days = (changed_at - started).days
            started = None
            every.append(days)
            corp_id = primary_corp.get(user_id)
            if corp_id:
                by_corp[corp_id].append(days)

    def average(days: list[int]) -> dict[str, int]:
        return {"days": round(sum(days) / len(days)), "count": len(days)}

    return {
        "by_corp": {
            str(corp_id): average(days) for corp_id, days in by_corp.items()
        },
        "alliance": average(every) if every else None,
    }


def percentile(value: float, ordered: list) -> Optional[int]:
    """Mid-rank percentile of `value` among `ordered` (ties split evenly)."""
    if not ordered:
        return None
    below = bisect_left(ordered, value)
    equal = bisect_right(ordered, value) - below
    return round(100 * (below + equal / 2) / len(ordered))


def tier_index(pct: int) -> int:
    for index, bound in enumerate(TIER_BOUNDS):
        if pct < bound:
            return index
    return len(TIER_BOUNDS)


def compare_user(payload: dict | None, user_id: int) -> list[dict] | None:
    """Fleets, kills and voice tiers for one user, or None without data."""
    peers = ((payload or {}).get("hygiene") or {}).get("peers") or {}
    row = (peers.get("users") or {}).get(str(user_id))
    baseline = peers.get("baseline") or {}
    if row is None or not baseline:
        return None
    result = []
    for index, signal in enumerate(SIGNALS):
        pct = percentile(row[index], baseline.get(signal) or [])
        result.append(
            {
                "signal": signal,
                "tier": None if pct is None else TIER_KEYS[tier_index(pct)],
                "percentile": pct,
            }
        )
    return result


def corp_trial_length(
    payload: dict | None, corporation_id: Optional[int]
) -> Optional[dict]:
    """{"days", "count", "scope": "corporation" | "alliance"} or None."""
    lengths = ((payload or {}).get("hygiene") or {}).get("trial_lengths") or {}
    corp = (lengths.get("by_corp") or {}).get(str(corporation_id))
    if corp and corp.get("count", 0) >= MIN_TRIALS_FOR_AVERAGE:
        return {**corp, "scope": "corporation"}
    alliance = lengths.get("alliance")
    if alliance:
        return {**alliance, "scope": "alliance"}
    return None


# Trial decisions that mean the pilot already clears the approval bar
# (too_early: clears it but has not reached day 60).
ON_PACE_DECISIONS = frozenset({"approve", "too_early"})


def trial_row(payload: dict | None, user_id: int) -> Optional[dict]:
    """The user's row in the snapshot's trial review, if they are on trial."""
    trial = ((payload or {}).get("hygiene") or {}).get("trial") or {}
    for rows in (trial.get("buckets") or {}).values():
        for row in rows or []:
            if row.get("user_id") == user_id:
                return row
    return None
