from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any, Literal

import requests
import sentry_sdk
from django.db import NotSupportedError, OperationalError, transaction
from django.utils import timezone

from feed.constants import (
    R2Z2_BAN_PAUSE_WARN_SECONDS,
    R2Z2_BANNED_SLEEP_SECONDS,
    R2Z2_CATCHUP_GAP_WARN,
    R2Z2_LIVE_GAP_WARN,
    R2Z2_NOT_FOUND_SLEEP_MS,
    R2Z2_POLL_SOFT_TIME_LIMIT_SECONDS,
    R2Z2_RATE_LIMIT_SLEEP_SECONDS,
    R2Z2_SEQUENCE_URL,
    R2Z2_SUCCESS_SLEEP_MS,
    R2Z2_USER_AGENT,
)
from feed.helpers.capital_pings import maybe_notify_capital_kill
from feed.helpers.ingest import upsert_feed_killmail_from_r2z2
from feed.helpers.monitored_systems import get_monitored_system_ids
from feed.models import FeedR2z2Cursor

logger = logging.getLogger(__name__)

R2Z2_BASE = "https://r2z2.zkillboard.com/ephemeral"

CursorRole = Literal["live", "catchup"]


class R2Z2Throttled(Exception):
    def __init__(self, status: int, pause_seconds: float):
        self.status = status
        self.pause_seconds = pause_seconds
        super().__init__(f"R2Z2 HTTP {status}, pause {pause_seconds}s")


def _headers() -> dict[str, str]:
    return {"User-Agent": R2Z2_USER_AGENT, "Accept": "application/json"}


def _retry_after_seconds(
    response: requests.Response,
    *,
    default_seconds: float,
) -> float:
    """Prefer Retry-After when present; otherwise use the default."""
    retry_after = response.headers.get("Retry-After")
    if not retry_after:
        return default_seconds
    try:
        return float(retry_after)
    except ValueError:
        return default_seconds


def _iso(dt) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _empty_stats(*, outcome: str) -> dict[str, Any]:
    return {
        "outcome": outcome,
        "live_processed": 0,
        "catchup_processed": 0,
        "processed": 0,
        "inserted": 0,
        "discarded": 0,
        "errors": 0,
        "rate_limited": 0,
        "banned": 0,
        "capital_pings": 0,
        "capital_pings_age_skipped": 0,
        "live_sequence_id": 0,
        "catchup_sequence_id": 0,
        "live_gap": None,
        "catchup_gap": 0,
        "paused_until": None,
        "live_idle_until": None,
    }


def _attach_cursor_stats(
    stats: dict[str, Any], cursor: FeedR2z2Cursor
) -> None:
    stats["live_sequence_id"] = cursor.live_sequence_id
    stats["catchup_sequence_id"] = cursor.catchup_sequence_id
    stats["catchup_gap"] = max(
        0, cursor.live_sequence_id - cursor.catchup_sequence_id
    )
    stats["paused_until"] = _iso(cursor.paused_until)
    stats["live_idle_until"] = _iso(cursor.live_idle_until)
    stats["processed"] = stats["live_processed"] + stats["catchup_processed"]


def _warn_throttle(
    *,
    status: int,
    sequence: int,
    pause_seconds: float,
    paused_until,
    cursor: FeedR2z2Cursor,
) -> None:
    sentry_sdk.set_tag("r2z2", "poll")
    sentry_sdk.set_tag("r2z2.throttle", str(status))
    sentry_sdk.set_context(
        "r2z2",
        {
            "sequence": sequence,
            "pause_seconds": pause_seconds,
            "paused_until": _iso(paused_until),
            "live_sequence_id": cursor.live_sequence_id,
            "catchup_sequence_id": cursor.catchup_sequence_id,
            "catchup_gap": max(
                0, cursor.live_sequence_id - cursor.catchup_sequence_id
            ),
        },
    )
    logger.warning(
        "R2Z2 HTTP %s at sequence %s; paused_until=%s (%.0fs)",
        status,
        sequence,
        _iso(paused_until),
        pause_seconds,
    )


def _warn_gaps(stats: dict[str, Any], cursor: FeedR2z2Cursor) -> None:
    live_gap = stats.get("live_gap")
    catchup_gap = stats.get("catchup_gap") or 0
    sentry_sdk.set_tag("r2z2", "poll")
    sentry_sdk.set_context(
        "r2z2",
        {
            "live_sequence_id": cursor.live_sequence_id,
            "catchup_sequence_id": cursor.catchup_sequence_id,
            "live_gap": live_gap,
            "catchup_gap": catchup_gap,
            "paused_until": stats.get("paused_until"),
        },
    )
    if live_gap is not None and live_gap > R2Z2_LIVE_GAP_WARN:
        logger.warning(
            "R2Z2 live tip falling behind: live_gap=%s live_sequence_id=%s",
            live_gap,
            cursor.live_sequence_id,
        )
    if catchup_gap > R2Z2_CATCHUP_GAP_WARN:
        logger.warning(
            "R2Z2 catch-up lagging: catchup_gap=%s live=%s catchup=%s",
            catchup_gap,
            cursor.live_sequence_id,
            cursor.catchup_sequence_id,
        )
    if cursor.paused_until is not None:
        remaining = (cursor.paused_until - timezone.now()).total_seconds()
        if remaining >= R2Z2_BAN_PAUSE_WARN_SECONDS:
            logger.warning(
                "R2Z2 ban/pause remaining %.0fs (paused_until=%s)",
                remaining,
                _iso(cursor.paused_until),
            )


def fetch_latest_sequence() -> int:
    """Fetch tip sequence. Raises on throttle/errors (no long sleeps)."""
    response = requests.get(R2Z2_SEQUENCE_URL, headers=_headers(), timeout=30)
    if response.status_code in (429, 403):
        default = (
            float(R2Z2_RATE_LIMIT_SLEEP_SECONDS)
            if response.status_code == 429
            else float(R2Z2_BANNED_SLEEP_SECONDS)
        )
        pause = _retry_after_seconds(response, default_seconds=default)
        raise R2Z2Throttled(response.status_code, pause)
    response.raise_for_status()
    return int(response.json()["sequence"])


def fetch_sequence_payload(
    sequence_id: int,
) -> tuple[int, dict[str, Any] | None, float | None]:
    url = f"{R2Z2_BASE}/{sequence_id}.json"
    response = requests.get(url, headers=_headers(), timeout=30)
    if response.status_code == 404:
        return 404, None, None
    if response.status_code == 429:
        return (
            429,
            None,
            _retry_after_seconds(
                response, default_seconds=float(R2Z2_RATE_LIMIT_SLEEP_SECONDS)
            ),
        )
    if response.status_code == 403:
        return (
            403,
            None,
            _retry_after_seconds(
                response, default_seconds=float(R2Z2_BANNED_SLEEP_SECONDS)
            ),
        )
    response.raise_for_status()
    return 200, response.json(), None


def _lock_cursor() -> FeedR2z2Cursor:
    FeedR2z2Cursor.get_singleton()
    qs = FeedR2z2Cursor.objects
    try:
        return qs.select_for_update(nowait=True).get(pk=1)
    except NotSupportedError:
        return qs.select_for_update().get(pk=1)


def _enforce_request_spacing(cursor: FeedR2z2Cursor) -> None:
    if cursor.last_request_at is None:
        return
    elapsed = (timezone.now() - cursor.last_request_at).total_seconds()
    min_gap = R2Z2_SUCCESS_SLEEP_MS / 1000
    if elapsed < min_gap:
        time.sleep(min_gap - elapsed)


def _mark_request(cursor: FeedR2z2Cursor) -> None:
    cursor.last_request_at = timezone.now()
    cursor.save(update_fields=["last_request_at", "updated_at"])


def _set_paused(cursor: FeedR2z2Cursor, pause_seconds: float) -> None:
    cursor.paused_until = timezone.now() + timedelta(seconds=pause_seconds)
    cursor.save(update_fields=["paused_until", "updated_at"])


def _advance_cursor(
    cursor: FeedR2z2Cursor, *, role: CursorRole, sequence: int
) -> None:
    if role == "live":
        cursor.live_sequence_id = sequence
        cursor.last_sequence_id = sequence
        cursor.save(
            update_fields=[
                "live_sequence_id",
                "last_sequence_id",
                "updated_at",
            ]
        )
    else:
        cursor.catchup_sequence_id = sequence
        cursor.save(update_fields=["catchup_sequence_id", "updated_at"])


def _process_payload(
    payload: dict[str, Any],
    *,
    allowlist: frozenset[int],
    apply_age_gate: bool,
    stats: dict[str, Any],
    pending_capital: list[tuple[dict[str, Any], bool]],
) -> None:
    result = upsert_feed_killmail_from_r2z2(payload, allowlist=allowlist)
    if result:
        stats["inserted"] += 1
    else:
        stats["discarded"] += 1
    pending_capital.append((payload, apply_age_gate))


def _flush_capital_notifications(
    pending_capital: list[tuple[dict[str, Any], bool]],
    stats: dict[str, Any],
) -> None:
    for payload, apply_age_gate in pending_capital:
        try:
            notified = maybe_notify_capital_kill(
                payload,
                apply_age_gate=apply_age_gate,
            )
            if notified is True:
                stats["capital_pings"] += 1
            elif notified is None:
                stats["capital_pings_age_skipped"] += 1
        except Exception:
            logger.exception("Capital ping evaluation failed")


def _poll_phase(
    cursor: FeedR2z2Cursor,
    *,
    role: CursorRole,
    start_sequence: int,
    stop_before: int | None,
    deadline: float,
    allowlist: frozenset[int],
    stats: dict[str, Any],
    apply_age_gate: bool,
    pending_capital: list[tuple[dict[str, Any], bool]],
) -> str:
    """Fetch sequences until tip, throttle, budget, or stop_before.

    Returns: tip | budget | throttled | error | stopped
    """
    sequence = start_sequence
    processed_key = "live_processed" if role == "live" else "catchup_processed"

    while time.monotonic() < deadline:
        if stop_before is not None and sequence > stop_before:
            return "stopped"
        if role == "catchup" and cursor.live_idle_until is not None:
            if timezone.now() >= cursor.live_idle_until:
                return "stopped"

        _enforce_request_spacing(cursor)
        try:
            status, payload, retry_after = fetch_sequence_payload(sequence)
            _mark_request(cursor)
        except requests.RequestException as exc:
            _mark_request(cursor)
            logger.warning(
                "R2Z2 fetch error at sequence %s: %s", sequence, exc
            )
            stats["errors"] += 1
            return "error"

        if status == 429:
            pause = retry_after or float(R2Z2_RATE_LIMIT_SLEEP_SECONDS)
            _set_paused(cursor, pause)
            stats["rate_limited"] += 1
            _warn_throttle(
                status=429,
                sequence=sequence,
                pause_seconds=pause,
                paused_until=cursor.paused_until,
                cursor=cursor,
            )
            return "throttled"

        if status == 403:
            pause = retry_after or float(R2Z2_BANNED_SLEEP_SECONDS)
            _set_paused(cursor, pause)
            stats["banned"] += 1
            _warn_throttle(
                status=403,
                sequence=sequence,
                pause_seconds=pause,
                paused_until=cursor.paused_until,
                cursor=cursor,
            )
            return "throttled"

        if status == 404:
            if role == "live":
                cursor.live_idle_until = timezone.now() + timedelta(
                    milliseconds=R2Z2_NOT_FOUND_SLEEP_MS
                )
                cursor.save(update_fields=["live_idle_until", "updated_at"])
            return "tip"

        stats[processed_key] += 1
        _advance_cursor(cursor, role=role, sequence=sequence)
        if payload:
            _process_payload(
                payload,
                allowlist=allowlist,
                apply_age_gate=apply_age_gate,
                stats=stats,
                pending_capital=pending_capital,
            )

        sequence += 1
        time.sleep(R2Z2_SUCCESS_SLEEP_MS / 1000)

    return "budget"


def poll_r2z2_batch(  # noqa: C901
    *, max_seconds: float | None = None
) -> dict[str, Any]:
    """Orchestrate live-first then catch-up on leftover budget.

    Holds a DB row lock for the window so only one poller runs cluster-wide.
    Never sleeps for ban/cooldown windows — sets paused_until instead.
    Capital Discord/ESI runs after the cursor transaction commits.
    """
    budget = max_seconds or R2Z2_POLL_SOFT_TIME_LIMIT_SECONDS
    started = time.monotonic()
    deadline = started + budget
    stats = _empty_stats(outcome="ok")
    pending_capital: list[tuple[dict[str, Any], bool]] = []

    try:
        with transaction.atomic():
            try:
                cursor = _lock_cursor()
            except OperationalError:
                stats = _empty_stats(outcome="skipped_locked")
                logger.info("R2Z2 poll skipped_locked")
                return stats

            now = timezone.now()
            if cursor.paused_until is not None and cursor.paused_until > now:
                _attach_cursor_stats(stats, cursor)
                stats["outcome"] = "skipped_paused"
                logger.info("R2Z2 poll complete: %s", stats)
                return stats

            allowlist = get_monitored_system_ids()

            # Seed live tip from sequence.json on first run.
            if cursor.live_sequence_id <= 0:
                _enforce_request_spacing(cursor)
                try:
                    tip = fetch_latest_sequence()
                    _mark_request(cursor)
                except R2Z2Throttled as exc:
                    _mark_request(cursor)
                    _set_paused(cursor, exc.pause_seconds)
                    stats["outcome"] = (
                        "rate_limited" if exc.status == 429 else "banned"
                    )
                    if exc.status == 429:
                        stats["rate_limited"] = 1
                    else:
                        stats["banned"] = 1
                    _warn_throttle(
                        status=exc.status,
                        sequence=0,
                        pause_seconds=exc.pause_seconds,
                        paused_until=cursor.paused_until,
                        cursor=cursor,
                    )
                    _attach_cursor_stats(stats, cursor)
                    logger.info("R2Z2 poll complete: %s", stats)
                    return stats
                except requests.RequestException as exc:
                    _mark_request(cursor)
                    logger.warning("R2Z2 sequence.json fetch failed: %s", exc)
                    stats["errors"] += 1
                    _attach_cursor_stats(stats, cursor)
                    logger.info("R2Z2 poll complete: %s", stats)
                    return stats

                cursor.live_sequence_id = max(0, tip - 1)
                cursor.last_sequence_id = cursor.live_sequence_id
                # Fresh install: catch-up has nothing behind live after tip is ingested.
                if cursor.catchup_sequence_id <= 0:
                    cursor.catchup_sequence_id = tip
                cursor.save(
                    update_fields=[
                        "live_sequence_id",
                        "last_sequence_id",
                        "catchup_sequence_id",
                        "updated_at",
                    ]
                )

            live_start = cursor.live_sequence_id + 1
            live_result = _poll_phase(
                cursor,
                role="live",
                start_sequence=live_start,
                stop_before=None,
                deadline=deadline,
                allowlist=allowlist,
                stats=stats,
                # Age-gate live too: a gap (bot restart, feed backlog) makes
                # the live phase churn stale sequences, which must not ping.
                apply_age_gate=True,
                pending_capital=pending_capital,
            )

            if live_result == "throttled":
                stats["outcome"] = (
                    "banned" if stats["banned"] else "rate_limited"
                )
            elif (
                live_result == "tip"
                and cursor.catchup_sequence_id < cursor.live_sequence_id
                and time.monotonic() < deadline
            ):
                catchup_result = _poll_phase(
                    cursor,
                    role="catchup",
                    start_sequence=cursor.catchup_sequence_id + 1,
                    stop_before=cursor.live_sequence_id,
                    deadline=deadline,
                    allowlist=allowlist,
                    stats=stats,
                    apply_age_gate=True,
                    pending_capital=pending_capital,
                )
                if catchup_result == "throttled":
                    stats["outcome"] = (
                        "banned" if stats["banned"] else "rate_limited"
                    )

            if live_result == "tip" and stats["outcome"] == "ok":
                try:
                    _enforce_request_spacing(cursor)
                    latest = fetch_latest_sequence()
                    _mark_request(cursor)
                    stats["live_gap"] = max(
                        0, latest - cursor.live_sequence_id
                    )
                except R2Z2Throttled as exc:
                    _mark_request(cursor)
                    _set_paused(cursor, exc.pause_seconds)
                    stats["outcome"] = (
                        "rate_limited" if exc.status == 429 else "banned"
                    )
                    if exc.status == 429:
                        stats["rate_limited"] = 1
                    else:
                        stats["banned"] = 1
                except requests.RequestException:
                    stats["errors"] += 1

            _attach_cursor_stats(stats, cursor)
            _warn_gaps(stats, cursor)
    except OperationalError:
        stats = _empty_stats(outcome="skipped_locked")
        logger.info("R2Z2 poll skipped_locked")
        return stats

    _flush_capital_notifications(pending_capital, stats)
    _attach_cursor_stats(
        stats,
        FeedR2z2Cursor.get_singleton(),
    )
    logger.info("R2Z2 poll complete: %s", stats)
    return stats
