"""Helpers shared by the tribe activity query modules."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Iterable

from django.utils import timezone

from eveonline.helpers.characters.identity import (
    character_ids_for_users,
    owner_user_ids,
    primary_refs_for_users,
)
from tribes.reports.types import PeriodBounds

# Months scanned for a "best month" record.
BEST_MONTH_LOOKBACK_DAYS = 366

# Round numbers a running all-time total works towards.
MILESTONES = (
    10,
    25,
    50,
    100,
    250,
    500,
    1_000,
    2_500,
    5_000,
    10_000,
    25_000,
    50_000,
    100_000,
)


def period_window(period: PeriodBounds) -> tuple[datetime, datetime]:
    start = timezone.make_aware(
        datetime.combine(period.start, datetime.min.time())
    )
    end = timezone.make_aware(
        datetime.combine(period.end, datetime.max.time())
    )
    return start, end


def best_month_since() -> datetime:
    return timezone.now() - timedelta(days=BEST_MONTH_LOOKBACK_DAYS)


def best_month(
    stamps: Iterable[tuple[datetime | None, float]],
) -> dict | None:
    """
    Highest monthly total from (timestamp, amount) pairs.

    Bucketed in Python: TruncMonth on MySQL needs timezone tables loaded.
    """
    totals: Counter = Counter()
    for stamp, amount in stamps:
        if stamp is None:
            continue
        totals[stamp.strftime("%Y-%m")] += amount or 0
    if not totals:
        return None
    month, value = max(totals.items(), key=lambda item: (item[1], item[0]))
    return {"month": month, "value": value}


def next_milestone(value: float) -> int | None:
    for milestone in MILESTONES:
        if value < milestone:
            return milestone
    return None


def roster_characters_by_eve_id(user_ids: Iterable[int]) -> dict[int, int]:
    """Every character a set of users owns, EVE character id -> user id."""
    return character_ids_for_users(user_ids)


def characters_to_users(eve_ids: Iterable[int]) -> dict[int, int]:
    """EVE character id -> owning user id (see eveonline identity rule)."""
    return owner_user_ids(eve_ids)


def primary_characters(user_ids: Iterable[int]) -> dict[int, tuple[int, str]]:
    """User id -> (primary character id, name)."""
    return primary_refs_for_users(user_ids)


def person_rows(
    counts_by_user: dict[int, dict],
    sort_key: str,
) -> list[dict]:
    """Rows keyed by primary character, highest ``sort_key`` first."""
    primaries = primary_characters(counts_by_user)
    rows = []
    for user_id, values in counts_by_user.items():
        char_id, name = primaries.get(user_id, (None, ""))
        rows.append(
            {
                "user_id": user_id,
                "primary_character_id": char_id,
                "primary_character_name": name,
                **values,
            }
        )
    rows.sort(
        key=lambda row: (
            row.get(sort_key) or 0,
            row["primary_character_name"],
        ),
        reverse=True,
    )
    return rows
