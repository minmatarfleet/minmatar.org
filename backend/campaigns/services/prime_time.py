"""The hours a pilot actually plays, from what the campaign has seen."""

from __future__ import annotations

from campaigns.models import (
    Campaign,
    CampaignKillmailParticipant,
    CampaignSiteCompletion,
)


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
