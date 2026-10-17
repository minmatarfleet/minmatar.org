"""Posts, videos and streams by group members (Thinkspeak tribe)."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from creators.models import CreatorAccount, CreatorItem, CreatorItemKind
from posts.models import EvePost
from tribes.reports.queries.common import (
    period_window,
    person_rows,
    primary_characters,
)
from tribes.reports.roster import roster_user_ids
from tribes.reports.types import PeriodBounds, ReportScope

COLUMNS = ["primary_character_name", "pieces", "posts", "videos"]

VIDEO_KINDS = (
    CreatorItemKind.VIDEO,
    CreatorItemKind.VOD,
    CreatorItemKind.STREAM,
)
LATEST_WORK = 3
QUARTER_DAYS = 91
QUARTERS_SCANNED = 8


def _posts(user_ids):
    # date_posted is when the draft was created; there is no publish stamp.
    return EvePost.objects.filter(state="published", user_id__in=user_ids)


def _videos(user_ids):
    return CreatorItem.objects.filter(
        account__user_id__in=user_ids,
        kind__in=VIDEO_KINDS,
        published_at__isnull=False,
    )


def run_publishing_report(
    tribe_group, period: PeriodBounds, scope: ReportScope, params
):
    start, end = period_window(period)
    roster = roster_user_ids(tribe_group)

    by_user: dict[int, dict] = defaultdict(
        lambda: {"pieces": 0, "posts": 0, "videos": 0}
    )
    for user_id in (
        _posts(roster)
        .filter(date_posted__gte=start, date_posted__lte=end)
        .values_list("user_id", flat=True)
    ):
        by_user[user_id]["posts"] += 1
        by_user[user_id]["pieces"] += 1
    for user_id in (
        _videos(roster)
        .filter(published_at__gte=start, published_at__lte=end)
        .values_list("account__user_id", flat=True)
    ):
        by_user[user_id]["videos"] += 1
        by_user[user_id]["pieces"] += 1

    rows = person_rows(by_user, "pieces")
    totals = {
        "posts_published": sum(r["posts"] for r in rows),
        "videos": sum(r["videos"] for r in rows),
        "writers": sum(1 for r in rows if r["posts"]),
        "creators": CreatorAccount.objects.filter(user_id__in=roster)
        .values("user_id")
        .distinct()
        .count(),
    }
    return rows, totals, COLUMNS


def _best_quarter(stamps) -> int:
    """Most pieces in any of the last eight 91-day blocks."""
    now = timezone.now()
    counts = [0] * QUARTERS_SCANNED
    for stamp in stamps:
        index = max(0, (now - stamp).days) // QUARTER_DAYS
        if 0 <= index < QUARTERS_SCANNED:
            counts[index] += 1
    return max(counts)


def publishing_highlights(tribe_group, period: PeriodBounds) -> dict:
    roster = roster_user_ids(tribe_group)
    posts = list(
        _posts(roster)
        .order_by("-date_posted")[:LATEST_WORK]
        .values("id", "title", "date_posted", "user_id")
    )
    videos = list(
        _videos(roster)
        .order_by("-published_at")[:LATEST_WORK]
        .values(
            "kind",
            "title",
            "url",
            "thumbnail_url",
            "published_at",
            "account__user_id",
        )
    )
    work = [
        {
            "kind": "post",
            "title": p["title"],
            "post_id": p["id"],
            "url": "",
            "thumbnail_url": "",
            "published_at": p["date_posted"],
            "user_id": p["user_id"],
        }
        for p in posts
    ] + [
        {
            "kind": v["kind"],
            "title": v["title"],
            "post_id": None,
            "url": v["url"],
            "thumbnail_url": v["thumbnail_url"],
            "published_at": v["published_at"],
            "user_id": v["account__user_id"],
        }
        for v in videos
    ]
    work.sort(key=lambda w: w["published_at"], reverse=True)
    work = work[:LATEST_WORK]
    authors = primary_characters(w["user_id"] for w in work)

    since = timezone.now() - timedelta(days=QUARTER_DAYS * QUARTERS_SCANNED)
    stamps = list(
        _posts(roster)
        .filter(date_posted__gte=since)
        .values_list("date_posted", flat=True)
    ) + list(
        _videos(roster)
        .filter(published_at__gte=since)
        .values_list("published_at", flat=True)
    )
    return {
        "latest_work": [
            {
                **{k: v for k, v in w.items() if k != "user_id"},
                "published_at": w["published_at"].isoformat(),
                "author": authors.get(w["user_id"], (None, ""))[1],
            }
            for w in work
        ],
        "best_quarter": _best_quarter(stamps),
        "all_time": {
            "posts": _posts(roster).count(),
            "videos": _videos(roster).count(),
        },
    }
