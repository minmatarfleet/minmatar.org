"""Monthly active-member headcount for a tribe group."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from tribes.models import (
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipHistory,
)

HIST_MONTHS = 12


def _month_label(year: int, month: int) -> str:
    return datetime(year, month, 1).strftime("%b %Y")


def _month_points_and_ends(
    now: datetime, months: int
) -> tuple[list[dict[str, str]], list[datetime]]:
    hist_start = (now.replace(day=1) - relativedelta(months=months)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    month_points: list[dict[str, str]] = []
    month_ends: list[datetime] = []
    cursor = hist_start
    while cursor.year < now.year or (
        cursor.year == now.year and cursor.month < now.month
    ):
        month_points.append(
            {
                "month": f"{cursor.year:04d}-{cursor.month:02d}",
                "label": _month_label(cursor.year, cursor.month),
            }
        )
        month_ends.append(cursor + relativedelta(months=1))
        cursor = cursor + relativedelta(months=1)
    return month_points, month_ends


def _intervals_from_history(
    events: list[tuple[str, datetime]],
) -> list[tuple[datetime, datetime | None]]:
    spans: list[tuple[datetime, datetime | None]] = []
    current_start = None
    for to_status, changed_at in events:
        if to_status == TribeGroupMembership.STATUS_ACTIVE:
            current_start = changed_at
        elif (
            to_status == TribeGroupMembership.STATUS_INACTIVE
            and current_start is not None
        ):
            spans.append((current_start, changed_at))
            current_start = None
    if current_start is not None:
        spans.append((current_start, None))
    return spans


def _intervals_from_membership_row(
    row: dict[str, Any],
) -> list[tuple[datetime, datetime | None]]:
    start = row["approved_at"] or row["created_at"]
    if start is None:
        return []
    if row["status"] == TribeGroupMembership.STATUS_ACTIVE:
        return [(start, row["left_at"])]
    if row["left_at"] is not None:
        return [(start, row["left_at"])]
    return []


def _membership_active_intervals(
    tribe_group: TribeGroup,
) -> dict[int, list[tuple[datetime, datetime | None]]]:
    memberships = list(
        TribeGroupMembership.objects.filter(tribe_group=tribe_group).values(
            "id",
            "user_id",
            "status",
            "approved_at",
            "left_at",
            "created_at",
        )
    )
    history: dict[int, list[tuple[str, datetime]]] = defaultdict(list)
    membership_ids = [row["id"] for row in memberships]
    if membership_ids:
        for membership_id, to_status, changed_at in (
            TribeGroupMembershipHistory.objects.filter(
                membership_id__in=membership_ids
            )
            .order_by("changed_at")
            .values_list("membership_id", "to_status", "changed_at")
        ):
            if changed_at is not None:
                history[membership_id].append((to_status, changed_at))

    intervals: dict[int, list[tuple[datetime, datetime | None]]] = defaultdict(
        list
    )
    for row in memberships:
        user_id = row["user_id"]
        events = history.get(row["id"], [])
        if events:
            intervals[user_id].extend(_intervals_from_history(events))
            continue
        intervals[user_id].extend(_intervals_from_membership_row(row))
    return intervals


def _active_counts_at_month_ends(
    intervals: dict[int, list[tuple[datetime, datetime | None]]],
    month_ends: list[datetime],
) -> list[int]:
    counts = [0] * len(month_ends)
    for month_i, month_end in enumerate(month_ends):
        seen: set[int] = set()
        for user_id, spans in intervals.items():
            for start, end in spans:
                if start < month_end and (end is None or end >= month_end):
                    seen.add(user_id)
                    break
        counts[month_i] = len(seen)
    return counts


def group_membership_growth(
    tribe_group: TribeGroup,
    *,
    now: datetime | None = None,
    months: int = HIST_MONTHS,
) -> dict[str, Any]:
    """
    Unique users with an active membership in ``tribe_group`` at each
    completed month end (same interval logic as alliance health tribes_monthly).
    """
    now = now or timezone.now()
    month_points, month_ends = _month_points_and_ends(now, months)
    if not month_ends:
        return {"months": month_points, "counts": [0] * len(month_points)}

    intervals = _membership_active_intervals(tribe_group)
    counts = _active_counts_at_month_ends(intervals, month_ends)
    return {"months": month_points, "counts": counts}
