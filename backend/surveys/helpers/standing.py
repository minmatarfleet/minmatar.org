"""Relative-standing notes for the profile stat tiles.

Turns raw values into how a member compares to the alliance — "Above average",
"Top 1%", or a timezone's share of the membership. All queries are cheap
aggregates and individually guarded; a failure just yields an empty note.
"""

import logging

from django.contrib.auth.models import User

from eveonline.models import EvePlayer
from learning.models import UserLearningProgress
from timezones.services import home_counts

logger = logging.getLogger(__name__)


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


def timezone_note(home: str | None) -> str:
    """How large the member's home timezone cohort is (US, EU or AU from
    the timezones app), among members who hold timezone roles."""
    if not home:
        return ""
    try:
        counts = home_counts()
        total = sum(counts.values())
        if total < 5:
            return ""
        mine = counts.get(home, 0)
        if not mine:
            return ""
        share = round(100.0 * mine / total)
        note = f"{share}% of members"
        if mine == max(counts.values()):
            note += " · largest TZ"
        return note
    except Exception:  # pragma: no cover - defensive
        logger.debug("timezone_note failed", exc_info=True)
        return ""
