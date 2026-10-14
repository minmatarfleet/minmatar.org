"""What a pilot's own history says about them.

Streaks, and the hours they actually play. Both read the day rows the
materialiser writes, which is why they live apart from it: the materialiser
writes a day, these read across days.
"""

from __future__ import annotations

from datetime import date, timedelta

from campaigns.models import (
    Campaign,
    CampaignKillmailParticipant,
    CampaignParticipantDay,
    CampaignSiteCompletion,
)

# Long enough to cover any streak worth paying for.
STREAK_LOOKBACK_DAYS = 60


def prime_time_label(hour_utc: int) -> str:
    """The timezone a pilot plays in, from the hour they are most active.

    Uses the same codes a pilot picks for themselves on their profile, so the
    roster can show a stated and an observed prime time side by side without
    two vocabularies. The bands are EVE's, not the clock's: the alliance
    peaks at 19:00 UTC, which is European evening.
    """
    if 0 <= hour_utc < 8:
        return "US"
    if 8 <= hour_utc < 16:
        return "AP"
    return "EU"


def run_ending_on(active_days: set, day: date) -> int:
    """How many consecutive active days end on ``day``, inclusive."""
    length = 1
    cursor = day - timedelta(days=1)
    while cursor in active_days:
        length += 1
        cursor -= timedelta(days=1)
    return length


def streak_length(campaign, user_id: int, day) -> int:
    """The streak a pilot is on, counting the day being materialised.

    Read from the day rows already stored, so the days before this one have
    to exist: always materialise a window oldest first.
    """
    previous = set(
        CampaignParticipantDay.objects.filter(
            campaign=campaign,
            user_id=user_id,
            active=True,
            day__lt=day,
            day__gte=day - timedelta(days=STREAK_LOOKBACK_DAYS),
        ).values_list("day", flat=True)
    )
    return run_ending_on(previous, day)


def streaks(active_days: list[date], today: date) -> tuple[int, int]:
    """The streak a pilot is on now, and the best one they have had."""
    if not active_days:
        return 0, 0

    days = set(active_days)
    latest = max(days)

    # Yesterday still counts: the campaign day does not end until 11:00 UTC,
    # so a pilot who flew last night has not broken anything yet.
    current = (
        run_ending_on(days, latest)
        if latest in (today, today - timedelta(days=1))
        else 0
    )
    best = max(run_ending_on(days, day) for day in days)
    return current, max(best, current)


def observed_activity(campaign: Campaign, user_id: int) -> tuple[list, str]:
    """Which UTC hours a pilot actually plays, and their prime time.

    Stated prime time is often out of date or never filled in, so the roster
    shows what the campaign has seen as well: the hours this pilot got kills
    or ran sites in.
    """
    hours: dict[int, int] = {}

    kill_times = CampaignKillmailParticipant.objects.filter(
        killmail__campaign=campaign, user_id=user_id, enlisted=True
    ).values_list("killmail__killmail_time", flat=True)
    site_times = CampaignSiteCompletion.objects.filter(
        campaign=campaign, user_id=user_id
    ).values_list("occurred_at", flat=True)

    for moment in list(kill_times) + list(site_times):
        hours[moment.hour] = hours.get(moment.hour, 0) + 1

    if not hours:
        return [], ""

    ordered = [
        hour for hour, _ in sorted(hours.items(), key=lambda kv: -kv[1])
    ]
    return ordered[:6], prime_time_label(ordered[0])
