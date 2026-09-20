"""Advantage: exact where we can measure it, crowd-read where we cannot.

Advantage multiplies the victory points of every capture, and ESI exposes
none of it. Our own contribution is exact, because every advantage action by
a tracked pilot arrives as an LP payout. The absolute value has to be read by
a pilot in space and reported.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from campaigns.constants import (
    ADVANTAGE_DELTA_BY_SITE_KIND,
    ADVANTAGE_READING_HIDE_MINUTES,
    ADVANTAGE_READING_STALE_MINUTES,
)
from campaigns.models import (
    CampaignAdvantageReading,
    CampaignAdvantageState,
    CampaignSiteCompletion,
    CampaignSystem,
)

logger = logging.getLogger(__name__)

OUTLIER_TOLERANCE = 25.0
CONSENSUS_WINDOW_MINUTES = 90


def record_reading(
    campaign_system: CampaignSystem,
    user,
    our_pct: float,
    enemy_pct: float,
    source: str = "pilot",
) -> tuple[CampaignAdvantageReading, CampaignAdvantageState]:
    """Store a pilot's reading, holding it when it disagrees wildly.

    Returns the reading and the state it produced. Callers want both, and
    re-reading the state off the system would hand them the stale one that
    Django cached before the reading existed.
    """
    status = "accepted"

    window = timezone.now() - timedelta(minutes=CONSENSUS_WINDOW_MINUTES)
    others = (
        CampaignAdvantageReading.objects.filter(
            campaign_system=campaign_system,
            status="accepted",
            reported_at__gte=window,
        )
        .exclude(reported_by=user)
        .exists()
    )

    if others and source != "manager":
        agreed_ours, agreed_theirs = _consensus(campaign_system, window)
        if (
            abs(our_pct - agreed_ours) > OUTLIER_TOLERANCE
            or abs(enemy_pct - agreed_theirs) > OUTLIER_TOLERANCE
        ):
            status = "held"

    reading = CampaignAdvantageReading.objects.create(
        campaign_system=campaign_system,
        reported_by=user,
        our_pct=max(0.0, min(100.0, our_pct)),
        enemy_pct=max(0.0, min(100.0, enemy_pct)),
        source=source,
        status=status,
    )
    return reading, recompute_state(campaign_system)


def recompute_state(campaign_system: CampaignSystem) -> CampaignAdvantageState:
    """Consensus reading, aged, with our measured contribution since."""
    now = timezone.now()
    latest = (
        CampaignAdvantageReading.objects.filter(
            campaign_system=campaign_system, status="accepted"
        )
        .order_by("-reported_at")
        .first()
    )

    state, _ = CampaignAdvantageState.objects.get_or_create(
        campaign_system=campaign_system
    )

    if not latest:
        state.basis = "unknown"
        state.our_pct = 0
        state.enemy_pct = 0
        state.reading_age_minutes = None
    else:
        age = int((now - latest.reported_at).total_seconds() // 60)
        if age > ADVANTAGE_READING_HIDE_MINUTES:
            state.basis = "unknown"
            state.reading_age_minutes = age
        else:
            window = latest.reported_at - timedelta(
                minutes=CONSENSUS_WINDOW_MINUTES
            )
            consensus = _consensus(campaign_system, window)
            state.our_pct = round(consensus[0] or latest.our_pct, 1)
            state.enemy_pct = round(consensus[1] or latest.enemy_pct, 1)
            state.reading_age_minutes = age
            state.basis = (
                "reading"
                if age <= ADVANTAGE_READING_STALE_MINUTES
                else "estimate"
            )

    generated, removed = contribution_since(
        campaign_system, latest.reported_at if latest else None
    )
    state.our_generated_since_reading = generated
    state.enemy_removed_since_reading = removed
    state.as_of = now
    state.save()

    # Django caches a reverse one-to-one on the instance, so anything still
    # holding this campaign_system would otherwise keep seeing the state as
    # it was before this reading.
    campaign_system.advantage_state = state
    return state


def _consensus(campaign_system, window) -> tuple[float, float]:
    """The agreed reading, counting each pilot once.

    Averaging every row would let one pilot who taps Report twenty times
    outvote the rest of the alliance, so only each reporter's most recent
    reading in the window is counted.
    """
    latest_per_pilot: dict = {}
    rows = CampaignAdvantageReading.objects.filter(
        campaign_system=campaign_system,
        status="accepted",
        reported_at__gte=window,
    ).order_by("reported_at")

    for reading in rows:
        latest_per_pilot[reading.reported_by_id] = reading

    if not latest_per_pilot:
        return (0.0, 0.0)

    readings = list(latest_per_pilot.values())
    ours = sum(reading.our_pct for reading in readings) / len(readings)
    theirs = sum(reading.enemy_pct for reading in readings) / len(readings)
    return (ours, theirs)


def contribution_since(
    campaign_system: CampaignSystem, since
) -> tuple[float, float]:
    """Advantage our tracked pilots generated and removed since a moment."""
    queryset = CampaignSiteCompletion.objects.filter(
        campaign_system=campaign_system, scored=True
    )
    if since:
        queryset = queryset.filter(occurred_at__gte=since)

    generated = 0.0
    removed = 0.0
    for site_kind, count in (
        queryset.values_list("site_kind")
        .annotate(n=Count("id"))
        .values_list("site_kind", "n")
    ):
        ours, theirs = ADVANTAGE_DELTA_BY_SITE_KIND.get(site_kind, (0.0, 0.0))
        generated += ours * count
        removed += theirs * count
    return round(generated, 1), round(removed, 1)


def as_card(state: CampaignAdvantageState | None) -> dict:
    """What a system card shows, with the estimate clearly labelled."""
    if state is None:
        return {
            "basis": "unknown",
            "our_pct": None,
            "enemy_pct": None,
            "net_pct": None,
            "reading_age_minutes": None,
            "is_stale": True,
            "our_generated_since_reading": 0,
            "enemy_removed_since_reading": 0,
        }
    return {
        "basis": state.basis,
        "our_pct": state.our_pct if state.basis != "unknown" else None,
        "enemy_pct": state.enemy_pct if state.basis != "unknown" else None,
        "net_pct": state.net_pct if state.basis != "unknown" else None,
        "reading_age_minutes": state.reading_age_minutes,
        "is_stale": state.is_stale,
        "our_generated_since_reading": state.our_generated_since_reading,
        "enemy_removed_since_reading": state.enemy_removed_since_reading,
    }


def card_for(campaign_system: CampaignSystem) -> dict:
    """The card for a system, read off whatever state it currently has."""
    return as_card(getattr(campaign_system, "advantage_state", None))
