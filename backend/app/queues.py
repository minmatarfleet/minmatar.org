"""Celery queues: what each one is for, and which tasks go where.

This module is the only place that decides a task's queue. Task decorators,
beat entries and ``apply_async`` call sites never pass ``queue=``; the
router in ``app.celery`` asks ``queue_for_task`` instead, which also covers
``send_task`` and beat. ``app/tests/test_queue_standards.py`` enforces it.

- ``celery`` (the default queue) is the fast lane: critical work someone is
  waiting on that finishes in seconds. A task only runs there when it is
  listed in ``FAST_TASKS``. Keep that list short.
- Every other task runs on its feature's queue, picked by the longest
  matching prefix in ``ROUTES``.

See docs/architecture/celery-queues.md for the standards and for adding a
queue.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

FAST_LANE = "celery"


@dataclass(frozen=True)
class QueueSpec:
    name: str
    purpose: str
    # Oldest message waiting longer than this raises a Sentry warning.
    max_wait_seconds: int
    # How long a queued copy holds its dedupe lock when the task sets no
    # ``expires``. Short on fast queues, so a lost message can't block the
    # next copy for long.
    dedupe_ttl_seconds: int


QUEUES: dict[str, QueueSpec] = {
    spec.name: spec
    for spec in (
        QueueSpec(
            FAST_LANE,
            "Fast lane: critical, user-facing work that finishes in seconds",
            max_wait_seconds=60,
            dedupe_ttl_seconds=5 * 60,
        ),
        QueueSpec(
            "feed",
            "zKillboard feed: live poll, rollups, clusters, affiliations",
            max_wait_seconds=2 * 60,
            dedupe_ttl_seconds=5 * 60,
        ),
        QueueSpec(
            "intel",
            "Intel affiliation database: sightings, zKill investigations",
            max_wait_seconds=30 * 60,
            dedupe_ttl_seconds=60 * 60,
        ),
        QueueSpec(
            "fleets",
            "Fleet tracking, implants, NPSI calendars, fleet reports",
            max_wait_seconds=2 * 60,
            dedupe_ttl_seconds=10 * 60,
        ),
        QueueSpec(
            "campaigns",
            "FW campaigns: sweeps, polls, stats, lifecycle",
            max_wait_seconds=15 * 60,
            dedupe_ttl_seconds=60 * 60,
        ),
        QueueSpec(
            "eveonline",
            "ESI sync for characters, corporations, structures, tokens, SDE",
            max_wait_seconds=30 * 60,
            dedupe_ttl_seconds=60 * 60,
        ),
        QueueSpec(
            "market",
            "Market orders, contracts, prices, history, moon revenue",
            max_wait_seconds=30 * 60,
            dedupe_ttl_seconds=60 * 60,
        ),
        QueueSpec(
            "industry",
            "Industry orders and jobs, LP store, LP and item buyback",
            max_wait_seconds=30 * 60,
            dedupe_ttl_seconds=60 * 60,
        ),
        QueueSpec(
            "community",
            "Discord, groups, tribes, applications, content and upkeep",
            max_wait_seconds=30 * 60,
            dedupe_ttl_seconds=60 * 60,
        ),
    )
}

# Critical work someone is waiting on. A task belongs here only when all
# three hold: a person or a live event is waiting on it, it finishes in a
# few seconds (one Discord or notification call, no ESI sync), and it never
# fans out. Everything else goes to its feature queue.
FAST_TASKS = frozenset(
    {
        # Discord outbox and notification delivery
        "discord.outbox.post_discord_message_task",
        "discord.outbox.send_discord_dm_task",
        "notifications.tasks.deliver_notification",
        # Discord threads for something a pilot just did
        "applications.tasks.sync_application_thread_task",
        "applications.tasks.notify_application_transferred_task",
        "applications.tasks.close_deleted_application_thread_task",
        "buyback.discord_tasks.notify_buyback_purchase_created_task",
        "buyback.discord_tasks.notify_buyback_purchase_status_changed_task",
        "buyback.discord_tasks.close_buyback_purchase_thread_task",
        "industry.tasks.notify_lp_buyback_order_created_task",
        "industry.tasks.notify_lp_buyback_order_status_changed_task",
        "industry.tasks.notify_lp_buyback_order_claimed_task",
        "industry.tasks.notify_lp_buyback_order_claims_released_task",
        "industry.tasks.notify_lp_buyback_order_cancelled_task",
        "industry.tasks.close_lp_buyback_discord_thread_task",
        "industry.tasks.emit_order_created_notification",
        # A CEO just added the bot and Settings waits for the first invite
        # (a few Discord calls for one corporation, no fan-out)
        "eveonline.tasks.corporations.refresh_corporation_discord_bot",
        # Fleet pings that are useless late
        "fleets.tasks.update_fleet_schedule",
        "fleets.tasks.nudge_missing_signups",
        # A pilot joined a tribe and is waiting for the Discord role
        "tribes.tasks.sync_external_guild_for_membership",
        # Measures every queue, so it must not wait behind any of them
        "app.tasks.monitor_queue_health",
    }
)

# Task-name prefix -> queue. The longest matching prefix wins.
ROUTES: dict[str, str] = {
    "feed.": "feed",
    "fleets.": "fleets",
    "intel.": "intel",
    "campaigns.": "campaigns",
    "eveonline.": "eveonline",
    "structures.": "eveonline",
    "esi.": "eveonline",
    "eveuniverse.": "eveonline",
    "eveuniverse.tasks.update_market_prices": "market",
    "eveuniverse.tasks._fetch_market_prices_esi": "market",
    "eveuniverse.tasks._update_market_prices_from_data": "market",
    "market.": "market",
    "moons.": "market",
    "industry.": "industry",
    "buyback.": "industry",
    "discord.": "community",
    "groups.": "community",
    "tribes.": "community",
    "applications.": "community",
    "notifications.": "community",
    "reddit.": "community",
    "creators.": "community",
    "reminders.": "community",
    "surveys.": "community",
    "alliance.": "community",
    "fittings.": "community",
    "capabilities.": "community",
    "app.": "community",
    # Celery's built-ins (backend_cleanup, chord_unlock)
    "celery.": "community",
}

# Where a task with no route goes. test_queue_standards fails for any
# registered task that lands here, so this only catches send_task names.
FALLBACK_QUEUE = "community"


def matched_route(task_name: str) -> str | None:
    """The queue a task routes to, or None when nothing matches."""
    if task_name in FAST_TASKS:
        return FAST_LANE
    best = ""
    for prefix in ROUTES:
        if task_name.startswith(prefix) and len(prefix) > len(best):
            best = prefix
    return ROUTES[best] if best else None


def queue_for_task(task_name: str) -> str:
    queue = matched_route(task_name)
    if queue is None:
        logger.warning(
            "No queue route for %s; sending it to %s",
            task_name,
            FALLBACK_QUEUE,
        )
        return FALLBACK_QUEUE
    return queue


def route_task(name, args, kwargs, options, task=None, **kw):
    """Celery router (``task_routes``) backed by the registry above."""
    del args, kwargs, options, task, kw
    return {"queue": queue_for_task(name)}
