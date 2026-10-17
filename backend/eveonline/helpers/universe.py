"""EveType helpers every app shares.

This is the lowest layer (eveuniverse plus eveonline.client), so buyback,
market and industry can all use it without importing each other.
"""

from __future__ import annotations

import logging
from typing import Iterable

from eveuniverse.models import EveType

from eveonline.client import live_esi_allowed

logger = logging.getLogger(__name__)


def ensure_eve_types(
    type_ids: Iterable[int], *, raise_on_error: bool = False
) -> dict[int, EveType]:
    """Load missing EveType rows from ESI; return id -> EveType for all known.

    Checks the database in one query and calls ESI only for missing ids.
    Skips ESI when ``live_esi_allowed()`` is false (unit tests), so the
    result then holds only the rows already stored. With
    ``raise_on_error`` the first ESI failure propagates; otherwise it is
    logged and that id is left out.
    """
    unique = sorted({int(t) for t in type_ids if t and int(t) > 0})
    if not unique:
        return {}
    found = {t.id: t for t in EveType.objects.filter(id__in=unique)}
    missing = [type_id for type_id in unique if type_id not in found]
    if not missing:
        return found
    if not live_esi_allowed():
        logger.info(
            "Skipping ESI load for %s missing EveType(s): live ESI is off",
            len(missing),
        )
        return found
    loaded = 0
    for type_id in missing:
        try:
            eve_type, _ = EveType.objects.get_or_create_esi(id=type_id)
        except Exception:  # noqa: BLE001 — ESI / SDE edge cases
            if raise_on_error:
                raise
            logger.warning(
                "Could not load EveType %s from ESI", type_id, exc_info=True
            )
            continue
        if eve_type is not None:
            found[type_id] = eve_type
            loaded += 1
    if loaded:
        logger.info("Loaded %s missing EveType(s) from ESI", loaded)
    return found
