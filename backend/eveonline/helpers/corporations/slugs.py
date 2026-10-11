"""Readable URL slugs for corporation pages.

EVE corporation names are unique and effectively permanent, so the slug is
derived from the name instead of stored. Keep `corporation_slug` in step with
`corporation_slug` in frontend/app/src/helpers/corporations/detail.ts.
"""

from __future__ import annotations

import re

from eveonline.models import EveCorporation

FL33T_ID = 99011978
BUILD_ID = 99012009

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def corporation_slug(name: str | None) -> str:
    return _NON_ALNUM.sub("-", (name or "").lower()).strip("-")


def corporation_for_slug(slug: str) -> EveCorporation | None:
    """Corporation whose name slugifies to `slug`.

    Names that differ only in punctuation share a slug; alliance corps win,
    then associates, then the oldest corporation ID.
    """
    if not _SLUG.match(slug or ""):
        return None
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
    rank = {FL33T_ID: 0, BUILD_ID: 1}.get(alliance_id, 2)
    return (rank, corporation.corporation_id)
