"""Cached 90-day corporation stats for the public profile.

The aggregates (fleets and kills by weekday, the At a glance
summary, application pace) scan fleet attendance, killmails and skills, so
they are far too slow to compute inside a page request. Celery refreshes
them on a schedule; a request only ever reads the cache and, on a miss,
queues one refresh and renders without them.
"""

from __future__ import annotations

import logging

from app.cache import CachedRollup
from eveonline.helpers.corporations.about import (
    corporation_about,
    member_facts,
)
from eveonline.helpers.corporations.activity import activity_for_characters
from eveonline.helpers.corporations.applications import application_process
from eveonline.helpers.corporations.kills import RecentKills
from eveonline.helpers.corporations.summary import corporation_public_summary
from eveonline.helpers.corporations.weekdays import weekday_distribution
from eveonline.models import EveCharacter, EveCorporation
from timezones.services import brackets_for

logger = logging.getLogger(__name__)

STATS_TTL_SECONDS = 6 * 60 * 60
REFRESH_LOCK_SECONDS = 10 * 60
_STATS_KEY = "corporation_profile_stats:v3:{corporation_id}"
_LOCK_KEY = "corporation_profile_stats:refreshing:{corporation_id}"


def _queue_refresh(corporation_id: int) -> None:
    # Imported here: the task module imports this helper.
    from eveonline.tasks.corporations import (  # pylint: disable=import-outside-toplevel
        refresh_corporation_profile_stats,
    )

    refresh_corporation_profile_stats.apply_async(args=[corporation_id])


STATS = CachedRollup(
    key=_STATS_KEY,
    ttl=STATS_TTL_SECONDS,
    lock_key=_LOCK_KEY,
    lock_ttl=REFRESH_LOCK_SECONDS,
    enqueue=_queue_refresh,
)


def compute_corporation_stats(
    corporation: EveCorporation, kills: RecentKills | None = None
) -> dict:
    """Everything slow on the corporation page, for the cache.

    `kills` may be preloaded for many corporations (see the refresh task).
    """
    characters = list(
        EveCharacter.objects.filter(
            corporation_id=corporation.corporation_id
        ).only("character_id", "user_id")
    )
    if kills is None:
        kills = RecentKills([c.character_id for c in characters])
    user_ids = list({c.user_id for c in characters if c.user_id})
    return {
        "about": corporation_about(
            corporation, characters, brackets_for(user_ids)
        ),
        "member_facts": member_facts(characters, corporation),
        "human_count": len(user_ids),
        # Per character fleets / kills / voice for the Members endpoints.
        "member_activity": activity_for_characters(characters, kills),
        "weekday_distribution": weekday_distribution(
            user_ids, corporation.corporation_id, kills=kills
        ),
        "public_summary": corporation_public_summary(corporation, kills),
        "application_process": application_process(corporation.corporation_id),
    }


def refresh_corporation_stats(
    corporation: EveCorporation, kills: RecentKills | None = None
) -> dict:
    stats = compute_corporation_stats(corporation, kills)
    STATS.store(stats, corporation_id=corporation.corporation_id)
    return stats


def corporation_stats(corporation_id: int) -> dict | None:
    """Cached stats, or None after queueing a refresh. Never computes inline."""
    return STATS.get_or_queue(corporation_id=corporation_id)
