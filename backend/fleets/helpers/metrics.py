"""What counts as leading a fleet, for every 'fleets led' number.

An FC led a fleet when they created it, it was not cancelled, and it is a
scheduled fleet rather than a campaign standing fleet or gang (those are
never scheduled and are scored by campaigns separately). Pending fleets
count, as they always have on the fleets page, whether or not the in-game
fleet was ever tracked.

Used by the fleets commander metrics, the tribe FC report, the corp About
leaderboard and the survey 'fc' flag. Campaigns keep their own per-day
count (campaigns.services.fleets.attendance_for_day), which only counts
fleets with an ESI instance up that day.

Attendance ('fleets attended') is counted per scheduled fleet on some
surfaces and per ESI fleet instance on others. Each EveFleet has had at
most one instance in production, so the two agree; see the docstrings at
alliance.helpers.health and eveonline.helpers.corporations.activity.
"""

from __future__ import annotations

from datetime import datetime

from django.db.models import Count, QuerySet

from fleets.models import CAMPAIGN_FLEET_TYPES, EveFleet


def led_fleets(
    start: datetime | None = None,
    end: datetime | None = None,
    *,
    include_campaign: bool = False,
) -> QuerySet:
    """Fleets that count as led, starting in ``[start, end)``."""
    fleets = EveFleet.objects.filter(created_by_id__isnull=False).exclude(
        status="cancelled"
    )
    if not include_campaign:
        fleets = fleets.exclude(type__in=CAMPAIGN_FLEET_TYPES)
    if start is not None:
        fleets = fleets.filter(start_time__gte=start)
    if end is not None:
        fleets = fleets.filter(start_time__lt=end)
    return fleets


def fleets_led_by_user(fleets: QuerySet) -> QuerySet:
    """``created_by_id`` and ``fleet_count`` rows, most fleets first."""
    return (
        fleets.values("created_by_id")
        .annotate(fleet_count=Count("id"))
        .order_by("-fleet_count", "created_by_id")
    )
