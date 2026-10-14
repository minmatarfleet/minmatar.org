"""Cached 90-day corporation stats for the public profile.

The aggregates (timezones, fleets and kills by weekday, the At a glance
summary, application pace) scan fleet attendance, killmails and skills, so
they are far too slow to compute inside a page request. Celery refreshes
them on a schedule; a request only ever reads the cache and, on a miss,
queues one refresh and renders without them.
"""

from __future__ import annotations

import logging


from eveonline.helpers.corporations.activity import activity_for_characters
from eveonline.helpers.corporations.applications import application_process
from eveonline.helpers.corporations.kills import RecentKills
from eveonline.helpers.corporations.summary import corporation_public_summary
from eveonline.helpers.corporations.timezones import (
    observed_prime_buckets_for_users,
    prime_time_codes_for_users,
    timezone_distribution,
    weekday_distribution,
)
from eveonline.helpers.corporations.safe_cache import (
    cache_add,
    cache_delete,
    cache_get,
    cache_set,
)
from eveonline.models import EveCharacter, EveCorporation

logger = logging.getLogger(__name__)

STATS_TTL_SECONDS = 6 * 60 * 60
REFRESH_LOCK_SECONDS = 10 * 60
_STATS_KEY = "corporation_profile_stats:v1:{corporation_id}"
_LOCK_KEY = "corporation_profile_stats:refreshing:{corporation_id}"


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
    # Leaders can be linked only through a token, or have their main outside
    # the corp, so include their accounts for the leadership tags too.
    from eveonline.helpers.corporations.profile import (  # pylint: disable=import-outside-toplevel
        leadership_rows,
    )

    leader_ids = {
        row["user_id"]
        for row in leadership_rows(corporation)
        if row.get("user_id")
    }
    timezone_users = list(set(user_ids) | leader_ids)
    declared = prime_time_codes_for_users(timezone_users)
    observed = observed_prime_buckets_for_users(timezone_users)
    return {
        "human_count": len(user_ids),
        # Per person, for leadership tags and the Members table.
        "declared_by_user": declared,
        "observed_by_user": observed,
        # Per character fleets / kills / voice for the Members endpoints.
        "member_activity": activity_for_characters(characters, kills),
        "timezone_distribution": timezone_distribution(
            user_ids, declared, observed
        ),
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
    cache_set(
        _STATS_KEY.format(corporation_id=corporation.corporation_id),
        stats,
        STATS_TTL_SECONDS,
    )
    cache_delete(_LOCK_KEY.format(corporation_id=corporation.corporation_id))
    return stats


def corporation_stats(corporation_id: int) -> dict | None:
    """Cached stats, or None after queueing a refresh. Never computes inline."""
    key = _STATS_KEY.format(corporation_id=corporation_id)
    stats = cache_get(key)
    if stats is not None:
        return stats
    # cache.add is atomic, so only one request per window queues the work.
    if cache_add(
        _LOCK_KEY.format(corporation_id=corporation_id),
        True,
        REFRESH_LOCK_SECONDS,
    ):
        _queue_refresh(corporation_id)
    # Eager Celery (tests) fills the cache during the call above.
    return cache_get(key)


def _queue_refresh(corporation_id: int) -> None:
    # Imported here: the task module imports this helper.
    from eveonline.tasks.corporations import (  # pylint: disable=import-outside-toplevel
        refresh_corporation_profile_stats,
    )

    try:
        refresh_corporation_profile_stats.apply_async(
            args=[corporation_id], queue="eveonline"
        )
    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Could not queue profile stats refresh for %s", corporation_id
        )
        cache_delete(_LOCK_KEY.format(corporation_id=corporation_id))
