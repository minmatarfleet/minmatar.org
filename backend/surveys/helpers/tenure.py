"""Derive a member's tenure. No single canonical join-date field exists, so we
fall back through the best available signals."""

import logging
from datetime import timedelta

from django.utils import timezone

from surveys.constants import (
    COHORT_EARLY,
    COHORT_ESTABLISHED,
    COHORT_NEW,
    COHORT_VETERAN,
)
from surveys.helpers.corp_history import alliance_join_date

logger = logging.getLogger(__name__)


def member_join_date(user):
    """Alliance corp-history join → community-status history →
    EvePlayer.created_at → date_joined."""
    # 1. Earliest ESI corporation-history start in an alliance corp — the true
    # "joined the community" date. Everything below is a fallback for members
    # whose corp history hasn't synced.
    try:
        joined = alliance_join_date(user)
        if joined:
            return joined
    except Exception:  # pragma: no cover - defensive
        logger.debug(
            "alliance_join_date lookup failed for %s", user, exc_info=True
        )

    # 2. Community status history. NOTE: this only goes back to when community
    # status tracking launched (2026-03-01), so it understates tenure for
    # members who joined earlier — hence it sits below corp history.
    try:
        first = (
            user.community_status_history.order_by("changed_at")
            .values_list("changed_at", flat=True)
            .first()
        )
        if first:
            return first
    except Exception:  # pragma: no cover - defensive
        logger.debug("no community_status_history for %s", user, exc_info=True)

    # 3. EvePlayer.created_at.
    try:
        player = getattr(user, "eveplayer", None)
        if player and player.created_at:
            return player.created_at
    except Exception:  # pragma: no cover - defensive
        pass

    # 4. Django account creation.
    return user.date_joined


def tenure_days(user) -> int | None:
    joined = member_join_date(user)
    if not joined:
        return None
    return max(0, (timezone.now() - joined).days)


def tenure_cohort(days: int | None) -> str:
    if days is None:
        return COHORT_NEW
    if days < 30:
        return COHORT_NEW
    if days < 90:
        return COHORT_EARLY
    if days < 365:
        return COHORT_ESTABLISHED
    return COHORT_VETERAN


def quarter_window(reference=None) -> tuple:
    """(start, end) datetimes for the trailing ~90 days."""
    end = reference or timezone.now()
    return end - timedelta(days=90), end
