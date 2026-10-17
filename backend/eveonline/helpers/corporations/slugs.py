"""Readable URL slugs for corporation pages.

EVE corporation names are unique and effectively permanent, so the slug is
derived from the name instead of stored. Keep `corporation_slug` in step with
`corporation_slug` in frontend/app/src/helpers/corporations/detail.ts.
"""

from __future__ import annotations

import re

from eveonline.constants import (
    MINMATAR_FLEET_ALLIANCE_ID,
    MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID,
)
from eveonline.helpers.alliances import member_corporations
from eveonline.helpers.corporations.safe_cache import cache_get, cache_set
from eveonline.models import EveCorporation

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SLUG_CACHE_KEY = "corporation_slug:v1:{slug}"
_SLUG_CACHE_SECONDS = 24 * 60 * 60


def corporation_slug(name: str | None) -> str:
    return _NON_ALNUM.sub("-", (name or "").lower()).strip("-")


def corporation_for_slug(slug: str) -> EveCorporation | None:
    """Corporation whose name slugifies to `slug`.

    Names that differ only in punctuation share a slug; alliance corps win,
    then associates, then the oldest corporation ID.
    """
    if not _SLUG.match(slug or ""):
        return None
    key = _SLUG_CACHE_KEY.format(slug=slug)
    cached_id = cache_get(key)
    if cached_id is not None:
        corporation = (
            EveCorporation.objects.select_related("alliance")
            .filter(corporation_id=cached_id)
            .first()
        )
        if corporation and corporation_slug(corporation.name) == slug:
            return corporation
    corporation = _find_by_slug(slug)
    if corporation is not None:
        cache_set(key, corporation.corporation_id, _SLUG_CACHE_SECONDS)
    return corporation


def _find_by_slug(slug: str) -> EveCorporation | None:
    # Alliance and associate corps cover nearly every page view and are a
    # small set; only fall back to scanning every corporation name.
    allied = [
        corporation
        for corporation in member_corporations().select_related("alliance")
        if corporation_slug(corporation.name) == slug
    ]
    if allied:
        return min(allied, key=_preference)
    words = slug.split("-")
    pattern = (
        r"^[^a-zA-Z0-9]*"
        + r"[^a-zA-Z0-9]+".join(re.escape(word) for word in words)
        + r"[^a-zA-Z0-9]*$"
    )
    candidates = [
        corporation
        for corporation in EveCorporation.objects.filter(
            name__iregex=pattern
        ).select_related("alliance")
        if corporation_slug(corporation.name) == slug
    ]
    if not candidates:
        return None
    return min(candidates, key=_preference)


def _preference(corporation: EveCorporation):
    alliance_id = (
        corporation.alliance.alliance_id if corporation.alliance else None
    )
    rank = {
        MINMATAR_FLEET_ALLIANCE_ID: 0,
        MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID: 1,
    }.get(alliance_id, 2)
    return (rank, corporation.corporation_id)
