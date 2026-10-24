"""EveType lookups every app shares: names to types, and loading missing types.

This is the lowest layer (eveuniverse plus eveonline.client), so buyback,
market and industry can all use it without importing each other.

Name resolution rules:

* Exact name first. A case-insensitive retry only runs when the caller asks
  for it (``case_insensitive=True``), so callers that relied on exact names
  keep exact names.
* ``published=None`` accepts any type; ``True``/``False`` keeps only those.
* Duplicate names are real: the SDE has about 130, mostly unpublished
  copies (``Infiltrator II`` 2175 published, 60376 not). A name resolves to
  its published type first, then the lowest type id. Before this module the
  winner was whichever row the database returned last.
* Unknown names map to ``None`` in ``resolve_types_by_name`` and are left
  out of ``type_ids_by_name``.
"""

from __future__ import annotations

import logging
from typing import Iterable

from eveuniverse.models import EveType

from eveonline.client import live_esi_allowed

logger = logging.getLogger(__name__)

_RELATED = ("eve_group", "eve_group__eve_category")


def _collision_key(published: bool, type_id: int) -> tuple[bool, int]:
    """Sort key for duplicate names: published first, then lowest id."""
    return (not published, type_id)


def _base_queryset(published: bool | None):
    queryset = EveType.objects.all()
    if published is not None:
        queryset = queryset.filter(published=published)
    return queryset


def resolve_types_by_name(
    names: Iterable[str],
    *,
    case_insensitive: bool = False,
    published: bool | None = None,
) -> dict[str, EveType | None]:
    """Map each distinct name to an EveType (group and category loaded).

    Every input name is a key; unknown names map to ``None``.
    """
    unique = list(dict.fromkeys(names))
    if not unique:
        return {}
    queryset = _base_queryset(published).select_related(*_RELATED)

    exact: dict[str, EveType] = {}
    for eve_type in queryset.filter(name__in=unique):
        best = exact.get(eve_type.name)
        if best is None or _collision_key(
            eve_type.published, eve_type.id
        ) < _collision_key(best.published, best.id):
            exact[eve_type.name] = eve_type

    result: dict[str, EveType | None] = {}
    for name in unique:
        eve_type = exact.get(name)
        if eve_type is None and case_insensitive:
            eve_type = (
                queryset.filter(name__iexact=name)
                .order_by("-published", "id")
                .first()
            )
        result[name] = eve_type
    return result


def type_ids_by_name(
    names: Iterable[str],
    *,
    case_insensitive: bool = False,
    published: bool | None = None,
) -> dict[str, int]:
    """Map each known name to a type id (unknown names are left out).

    Same rules as ``resolve_types_by_name`` without loading whole rows.
    """
    unique = list(dict.fromkeys(names))
    if not unique:
        return {}
    queryset = _base_queryset(published)

    best: dict[str, tuple[bool, int]] = {}
    for name, type_id, is_published in queryset.filter(
        name__in=unique
    ).values_list("name", "id", "published"):
        key = _collision_key(is_published, type_id)
        if name not in best or key < best[name]:
            best[name] = key

    result: dict[str, int] = {}
    for name in unique:
        if name in best:
            result[name] = best[name][1]
            continue
        if not case_insensitive:
            continue
        type_id = (
            queryset.filter(name__iexact=name)
            .order_by("-published", "id")
            .values_list("id", flat=True)
            .first()
        )
        if type_id is not None:
            result[name] = type_id
    return result


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
