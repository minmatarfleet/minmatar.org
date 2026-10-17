"""#help tickets resolved for a tribe group's help categories (Technology)."""

from __future__ import annotations

from collections import defaultdict
from statistics import median

from help_tickets.models import HelpTicket
from tribes.reports.queries.common import (
    best_month,
    best_month_since,
    period_window,
    person_rows,
    primary_characters,
)
from tribes.reports.types import PeriodBounds, ReportScope
from users.models import UserDesktopSettings

COLUMNS = [
    "primary_character_name",
    "tickets_resolved",
    "median_fix_hours",
]

FIXED_LIST = 5


def _closed(tribe_group):
    """Closed through the bot, so closed_at and closed_by are known."""
    return HelpTicket.objects.filter(
        category__tribe_group=tribe_group,
        status=HelpTicket.STATUS_CLOSED,
        closed_at__isnull=False,
    )


def _hours(opened_at, closed_at) -> float:
    return (closed_at - opened_at).total_seconds() / 3600


def run_help_desk_report(
    tribe_group, period: PeriodBounds, scope: ReportScope, params
):
    """
    Tickets in the group's categories. Whoever closed a ticket gets the
    credit, group member or not: the work is the group's queue.
    """
    start, end = period_window(period)
    tickets = list(
        _closed(tribe_group)
        .filter(closed_at__gte=start, closed_at__lte=end)
        .values_list(
            "opened_at", "closed_at", "closed_by_id", "opener_discord_id"
        )
    )

    fix_hours: dict[int, list[float]] = defaultdict(list)
    for opened_at, closed_at, closer, _ in tickets:
        if closer:
            fix_hours[closer].append(_hours(opened_at, closed_at))
    by_user = {
        user_id: {
            "tickets_resolved": len(hours),
            "median_fix_hours": round(median(hours), 1),
        }
        for user_id, hours in fix_hours.items()
    }
    all_hours = [_hours(o, c) for o, c, _, _ in tickets]
    totals = {
        "tickets_resolved": len(tickets),
        "median_fix_hours": round(median(all_hours), 1) if all_hours else 0,
        "pilots_helped": len({opener for _, _, _, opener in tickets}),
    }
    if params.get("desktop_app"):
        totals["desktop_app_pilots"] = UserDesktopSettings.objects.count()
    return person_rows(by_user, "tickets_resolved"), totals, COLUMNS


def help_desk_highlights(tribe_group, period: PeriodBounds) -> dict:
    start, end = period_window(period)
    closed = _closed(tribe_group)
    recent = list(
        closed.filter(closed_at__gte=start, closed_at__lte=end)
        .select_related("category")
        .order_by("-closed_at")[:FIXED_LIST]
    )
    # Thread names are slugs of the opener, so name the pilot instead.
    pilots = primary_characters(
        {t.closed_by_id for t in recent} | {t.opener_id for t in recent}
    )
    return {
        "fixed": [
            {
                "pilot_character_id": pilots.get(ticket.opener_id, (None,))[0],
                "pilot_name": pilots.get(ticket.opener_id, (None, ""))[1],
                "category": ticket.category.title,
                "closed_by": pilots.get(ticket.closed_by_id, (None, ""))[1],
                "hours": round(_hours(ticket.opened_at, ticket.closed_at), 1),
            }
            for ticket in recent
        ],
        "best_month": best_month(
            (at, 1)
            for at in closed.filter(
                closed_at__gte=best_month_since()
            ).values_list("closed_at", flat=True)
        ),
        "all_time": {
            "pilots_helped": closed.values("opener_discord_id")
            .distinct()
            .count(),
        },
    }
