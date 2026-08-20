"""Relative-standing notes for the profile stat tiles.

Turns raw values into how a member compares to the alliance — "Above average",
"Top 1%", or a timezone's share of the membership. All queries are cheap
aggregates and individually guarded; a failure just yields an empty note.
"""

import logging

from django.contrib.auth.models import User

from eveonline.models import EvePlayer
from learning.models import UserLearningProgress

logger = logging.getLogger(__name__)

PRIME_LABELS = {
    "US": "US",
    "US_AP": "US/AP",
    "AP": "AP",
    "AP_EU": "AP/EU",
    "EU": "EU",
    "EU_US": "EU/US",
}


def _band(percentile: float) -> str:
    """percentile = % of members this member is strictly ahead of."""
    if percentile >= 99:
        return "Top 1%"
    if percentile >= 75:
        return "Above average"
    if percentile >= 40:
        return "Average"
    return "Below average"


def tenure_note(join_date) -> str:
    if not join_date:
        return ""
    try:
        total = EvePlayer.objects.filter(created_at__isnull=False).count()
        if total < 5:
            return ""
        # Members who joined later than you have less tenure → you're ahead of them.
        newer = EvePlayer.objects.filter(created_at__gt=join_date).count()
        return _band(100.0 * newer / total)
    except Exception:  # pragma: no cover - defensive
        logger.debug("tenure_note failed", exc_info=True)
        return ""


def fleets_note(activity_tier: str) -> str:
    # Qualitative band from the already-computed activity tier (no heavy query).
    return {
        "core": "Top 1%",
        "regular": "Above average",
        "lapsing": "Average",
        "inactive": "Below average",
    }.get(activity_tier, "")


def guides_note(count: int) -> str:
    try:
        learners = (
            UserLearningProgress.objects.values("user").distinct().count()
        )
        if learners < 5:
            return ""
        total_members = User.objects.filter(is_active=True).count() or learners
        avg = UserLearningProgress.objects.count() / max(1, total_members)
        if count == 0:
            return "Below average"
        if count >= max(3, avg * 2):
            return "Top 1%"
        if count >= avg:
            return "Above average"
        if count >= max(1, avg * 0.4):
            return "Average"
        return "Below average"
    except Exception:  # pragma: no cover - defensive
        logger.debug("guides_note failed", exc_info=True)
        return ""


def timezone_note(prime_time: str) -> str:
    """Communicate how large the member's timezone cohort is."""
    if not prime_time:
        return ""
    try:
        rows = list(
            EvePlayer.objects.exclude(prime_time__isnull=True)
            .exclude(prime_time="")
            .values_list("prime_time", flat=True)
        )
        total = len(rows)
        if total < 5:
            return ""
        counts: dict[str, int] = {}
        for tz in rows:
            counts[tz] = counts.get(tz, 0) + 1
        mine = counts.get(prime_time, 0)
        if not mine:
            return ""
        share = round(100.0 * mine / total)
        ranked = sorted(counts.values(), reverse=True)
        note = f"{share}% of members"
        if counts[prime_time] == ranked[0]:
            note += " · largest TZ"
        return note
    except Exception:  # pragma: no cover - defensive
        logger.debug("timezone_note failed", exc_info=True)
        return ""
