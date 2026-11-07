"""What is waiting on one user across the manage screens.

Every queue is counts only: a few aggregate queries, no rows serialized.
A queue is listed only when the user can reach its screen, and counts only
what they may act on there.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import Count, Min
from django.utils import timezone

from eveonline.models import EveCharacterFwLpPayout, FwPayoutEventCode
from fittings.helpers.change_request_api import can_review_request
from fittings.models import (
    EveDoctrineChangeRequest,
    EveFitting,
    EveFittingChangeRequest,
)
from fleets.models import NpsiEventSource
from manage_hub.screens import Screen, reachable_screens
from reddit.models import RedditPostChangeRequest, RedditPostTemplate

# The payout-codes screen lists codes seen in this window
# (campaigns/endpoints/get_payout_codes.py).
PAYOUT_WINDOW_DAYS = 30


@dataclass
class QueueSummary:
    key: str
    screen: str
    count: int
    oldest_at: datetime | None = None
    # The item to look at first: a doctrine, corporation, code or feed name.
    next_label: str = ""
    tone: str = ""


def doctrine_changes(user) -> QueueSummary:
    """Pending doctrine and fitting change requests this user may review."""
    queue = QueueSummary("doctrine_changes", "doctrines", 0)
    # Per kind: (oldest submitted_at, kind, model, reviewable tiers).
    candidates = []
    for kind, model in (
        ("doctrine", EveDoctrineChangeRequest),
        ("fitting", EveFittingChangeRequest),
    ):
        tiers = (
            model.objects.filter(status="pending")
            .order_by()
            .values("tier")
            .annotate(n=Count("id"), first=Min("submitted_at"))
        )
        reviewable = [
            row for row in tiers if can_review_request(user, kind, row["tier"])
        ]
        if not reviewable:
            continue
        queue.count += sum(row["n"] for row in reviewable)
        candidates.append(
            (
                min(row["first"] for row in reviewable),
                kind,
                model,
                [row["tier"] for row in reviewable],
            )
        )
    if not candidates:
        return queue
    first, kind, model, tiers = min(candidates, key=lambda row: row[0])
    queue.oldest_at = first
    request = (
        model.objects.filter(status="pending", tier__in=tiers)
        .order_by("submitted_at")
        .first()
    )
    if request is not None and kind == "doctrine":
        queue.next_label = request.doctrine.name
    elif request is not None:
        queue.next_label = (
            EveFitting.all_objects.filter(pk=request.fitting_id)
            .values_list("name", flat=True)
            .first()
            or ""
        )
    return queue


def reddit_posts(*_) -> QueueSummary:
    """Reddit post changes and first-time posts waiting for approval.

    The same rows as the approvals queue (reddit/review_router.py).
    """
    queue = QueueSummary("reddit_posts", "reddit", 0)
    changes = list(
        RedditPostChangeRequest.objects.filter(
            status=RedditPostChangeRequest.PENDING
        ).values_list(
            "template_id", "created_at", "template__corporation__name"
        )
    )
    waiting = list(
        RedditPostTemplate.objects.filter(approved=False)
        .exclude(pk__in=[row[0] for row in changes])
        .exclude(title="")
        .values_list("pk", "updated_at", "corporation__name")
    )
    rows = [row for row in changes + waiting if row[1] is not None]
    queue.count = len(changes) + len(waiting)
    if rows:
        _, queue.oldest_at, queue.next_label = min(rows, key=lambda r: r[1])
    return queue


def payout_codes(*_) -> QueueSummary:
    """Payout codes seen in the last 30 days that map to no site kind."""
    queue = QueueSummary("payout_codes", "payout_codes", 0)
    since = timezone.now() - timedelta(days=PAYOUT_WINDOW_DAYS)
    unmapped = (
        EveCharacterFwLpPayout.objects.filter(
            occurred_at__gte=since, event_code__isnull=False
        )
        .exclude(event_code__in=FwPayoutEventCode.objects.values("event_code"))
        .order_by()
        .values("event_code")
        .annotate(first=Min("occurred_at"))
        .order_by("first")
    )
    rows = list(unmapped)
    queue.count = len(rows)
    if rows:
        queue.oldest_at = rows[0]["first"]
        queue.next_label = str(rows[0]["event_code"])
    return queue


def npsi_feeds(*_) -> QueueSummary:
    """Enabled NPSI feeds whose last poll failed.

    oldest_at is when the longest-failing feed last read cleanly (or was
    added, if it never has).
    """
    queue = QueueSummary("npsi_feeds", "npsi_feeds", 0, tone="warn")
    rows = list(
        NpsiEventSource.objects.filter(enabled=True)
        .exclude(last_error="")
        .values_list("name", "last_success_at", "created_at")
    )
    queue.count = len(rows)
    dated = [
        (since, name)
        for name, success, created in rows
        if (since := success or created) is not None
    ]
    if dated:
        queue.oldest_at, queue.next_label = min(dated)
    elif rows:
        queue.next_label = rows[0][0]
    return queue


# Queue key -> (screen, counter), in display order.
QUEUES = (
    ("doctrine_changes", "doctrines", doctrine_changes),
    ("reddit_posts", "reddit", reddit_posts),
    ("payout_codes", "payout_codes", payout_codes),
    ("npsi_feeds", "npsi_feeds", npsi_feeds),
)


def manage_summary(user) -> dict:
    screens: list[Screen] = reachable_screens(user)
    reachable = {screen.key for screen in screens}
    queues = [
        counter(user) for _, screen, counter in QUEUES if screen in reachable
    ]
    return {
        "role": "superuser" if user.is_superuser else "manager",
        "screens": [
            {"key": screen.key, "group": screen.group} for screen in screens
        ],
        "queues": [queue.__dict__ for queue in queues],
        "total": sum(queue.count for queue in queues),
    }
