"""Real names for alliance, corporation and character ids.

Unlike ``feed.helpers.eve_names``, an id ESI can't name is left out rather
than given a placeholder, so a placeholder is never saved as a name.
"""

from __future__ import annotations

from typing import Iterable

from intel.models import IntelEntity
from intel.services.local import ENTITY_NAME_TTL, _cached_lookup, _esi_names


def esi_names(ids: Iterable[int]) -> dict[int, str]:
    """The intel name cache (a day), then one bulk ESI call."""
    ids = {int(i) for i in ids if i}
    if not ids:
        return {}
    found = _cached_lookup(ids, "intel:entity:", _esi_names, ENTITY_NAME_TTL)
    return {k: v for k, v in (found or {}).items() if v}


def names_for(ids: Iterable[int]) -> dict[int, str]:
    """The names we keep first, then ``esi_names``."""
    ids = {int(i) for i in ids if i}
    names = dict(
        IntelEntity.objects.filter(eve_id__in=ids)
        .exclude(name="")
        .values_list("eve_id", "name")
    )
    names.update(esi_names(ids - names.keys()))
    return names
