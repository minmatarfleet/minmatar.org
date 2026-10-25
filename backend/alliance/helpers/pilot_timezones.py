"""Timezone tags for alliance health cards, from the timezones app."""

from __future__ import annotations

from collections.abc import Iterable

from django.conf import settings

from timezones.schemas import TimezoneTag
from timezones.services import timezone_tags_for

READONLY_ALIAS = "production_readonly"


def pilot_timezone_tags(user_ids: Iterable[int]) -> dict[int, TimezoneTag]:
    """Every asked user's tag. Snapshots computed from production data can
    name users this database has not assessed, so those fall back to the
    read-only production alias when it is configured."""
    ids = sorted({int(uid) for uid in user_ids if uid})
    if not ids:
        return {}
    tags = timezone_tags_for(ids)
    missing = [uid for uid in ids if not tags[uid].brackets]
    if missing and READONLY_ALIAS in settings.DATABASES:
        for user_id, tag in timezone_tags_for(
            missing, using=READONLY_ALIAS
        ).items():
            if tag.brackets:
                tags[user_id] = tag
    return tags
