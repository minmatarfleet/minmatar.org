"""Cheap in-place snapshot edits after community-status actions.

The hourly health snapshot is too expensive to rebuild after promote / leave /
restore. Drop the person from the cached lists and bump the headcounts so the
dashboard stays consistent until the next full refresh.
"""

from __future__ import annotations

import copy
from typing import Any

from alliance.helpers.health import is_gone_for_months_pilot, latest_snapshot
from groups.models import UserCommunityStatus

_ATTENTION_BUCKETS = ("fading", "dark", "seasonal")
_TRIAL_BUCKETS = (
    "approve",
    "too_early",
    "fail",
    "nudge",
    "hold",
    "current",
    "add",
    "remove",
    "flagged",
    "passing",
    "failing",
    "evaluating",
)
_LEAVE_LISTS = (
    "recommended",
    "current",
    "restore",
    "inactive",
    "returning",
    "flagged",
)


def _drop_user(rows: Any, user_id: int) -> Any:
    if not isinstance(rows, list):
        return rows
    return [row for row in rows if row.get("user_id") != user_id]


def _bump_status(
    payload: dict[str, Any], from_status: str | None, to_status: str
) -> None:
    status = payload.setdefault("status", {})
    if from_status:
        status[from_status] = max(0, int(status.get(from_status) or 0) - 1)
    status[to_status] = int(status.get(to_status) or 0) + 1


def _recount_quiet(payload: dict[str, Any]) -> None:
    attention = payload.get("attention") or {}
    payload["quiet"] = {
        "fading": len(attention.get("fading") or []),
        "dark": sum(
            1
            for row in attention.get("dark") or []
            if is_gone_for_months_pilot(
                row.get("days_quiet"), row.get("active_months")
            )
        ),
        "seasonal": len(attention.get("seasonal") or []),
    }


def _recount_hygiene_lists(payload: dict[str, Any]) -> None:
    hygiene = payload.get("hygiene") or {}
    trial = hygiene.get("trial") or {}
    buckets = trial.get("buckets") or {}
    if buckets:
        counts = trial.setdefault("counts", {})
        for key, rows in buckets.items():
            if isinstance(rows, list):
                counts[key] = len(rows)
    leave = hygiene.get("leave") or {}
    counts = leave.setdefault("counts", {})
    for key in _LEAVE_LISTS:
        rows = leave.get(key)
        if isinstance(rows, list):
            counts[key] = len(rows)
    if isinstance(leave.get("recommended"), list):
        counts["add"] = len(leave["recommended"])
    if isinstance(leave.get("restore"), list):
        counts["remove"] = len(leave["restore"])


def apply_status_change_to_latest_snapshot(
    user_id: int, action: str, from_status: str | None
) -> None:
    snap = latest_snapshot()
    if snap is None or not snap.payload:
        return
    payload = copy.deepcopy(snap.payload)

    attention = payload.setdefault("attention", {})
    for bucket in _ATTENTION_BUCKETS:
        attention[bucket] = _drop_user(attention.get(bucket), user_id)

    hygiene = payload.setdefault("hygiene", {})
    trial = hygiene.setdefault("trial", {})
    buckets = trial.setdefault("buckets", {})
    for key in _TRIAL_BUCKETS:
        buckets[key] = _drop_user(buckets.get(key), user_id)

    leave = hygiene.setdefault("leave", {})
    for key in _LEAVE_LISTS:
        leave[key] = _drop_user(leave.get(key), user_id)

    if action == "promote":
        _bump_status(
            payload,
            UserCommunityStatus.STATUS_TRIAL,
            UserCommunityStatus.STATUS_ACTIVE,
        )
    elif action == "leave":
        _bump_status(
            payload,
            from_status or UserCommunityStatus.STATUS_ACTIVE,
            UserCommunityStatus.STATUS_ON_LEAVE,
        )
    elif action == "restore":
        _bump_status(
            payload,
            UserCommunityStatus.STATUS_ON_LEAVE,
            UserCommunityStatus.STATUS_ACTIVE,
        )

    _recount_quiet(payload)
    _recount_hygiene_lists(payload)
    snap.payload = payload
    snap.save(update_fields=["payload"])
