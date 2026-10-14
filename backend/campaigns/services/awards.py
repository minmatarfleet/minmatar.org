"""Weekly and campaign awards.

A long campaign needs something to win every week, not only at the end, so
the six weekly awards are decided from the same participant-day rows the
boards read and announced on the campaign timeline.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.db.models import Sum
from django.utils import timezone

from campaigns.constants import CAMPAIGN_AWARDS, WEEKLY_AWARDS
from campaigns.helpers import campaign_week_start
from campaigns.models import (
    Campaign,
    CampaignAward,
    CampaignEvent,
    CampaignParticipantDay,
    CampaignParticipantStat,
)

logger = logging.getLogger(__name__)


def close_week(campaign: Campaign, week_start: date | None = None) -> int:
    """Decide the week's awards. Idempotent: a code is awarded once a week."""
    week_start = week_start or campaign_week_start()
    rows = CampaignParticipantDay.objects.filter(
        campaign=campaign, day__gte=week_start, day__lt=_next_week(week_start)
    )
    if not rows.exists():
        return 0

    awarded = 0
    for code, label, metric in WEEKLY_AWARDS:
        winner = _top(rows, metric)
        if not winner:
            continue

        _, created = CampaignAward.objects.get_or_create(
            campaign=campaign,
            code=code,
            week_start=week_start,
            defaults={
                "user_id": winner["user_id"],
                "label": label,
                "scope": "week",
                "payload": {"metric": metric, "value": winner["value"]},
            },
        )
        if created:
            awarded += 1
            _announce(campaign, label, winner, metric, week_start)

    return awarded


def close_campaign(campaign: Campaign) -> int:
    """The three awards that can only be decided once it is over."""
    stats = CampaignParticipantStat.objects.filter(campaign=campaign)
    if not stats.exists():
        return 0

    awarded = 0
    for code, label, metric in CAMPAIGN_AWARDS:
        winner = stats.order_by(f"-{metric}").first()
        if not winner or not getattr(winner, metric, 0):
            continue

        _, created = CampaignAward.objects.get_or_create(
            campaign=campaign,
            code=code,
            week_start=None,
            defaults={
                "user_id": winner.user_id,
                "label": label,
                "scope": "campaign",
                "payload": {
                    "metric": metric,
                    "value": getattr(winner, metric),
                },
            },
        )
        if created:
            awarded += 1

    return awarded


def _top(rows, metric: str) -> dict | None:
    """The pilot with the most of one metric, ignoring everyone on zero."""
    best = (
        rows.values("user_id", "user__username")
        .annotate(value=Sum(metric))
        .filter(value__gt=0)
        .order_by("-value")
        .first()
    )
    return best


def _announce(campaign, label, winner, metric, week_start) -> None:
    CampaignEvent.objects.create(
        campaign=campaign,
        kind=CampaignEvent.Kind.AWARD,
        occurred_at=timezone.now(),
        title=f"{label}: {winner['user__username']}",
        body=f"{winner['value']:g} {metric.replace('_', ' ')} this week.",
        user_id=winner["user_id"],
        side="friendly",
        payload={"week_start": week_start.isoformat(), "metric": metric},
    )


def _next_week(week_start: date) -> date:
    return week_start + timedelta(days=7)
