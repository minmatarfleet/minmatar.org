"""The intel tool's SDE-derived fixtures: ship types and the jump map.

Both are exported by ``manage.py export_intel_fixtures`` and read once per
process. Without them d-scans still save, every type just lands in
"Other", and the map endpoint returns an empty graph.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


def types_fixture_path() -> Path:
    return Path(settings.BASE_DIR) / "intel" / "fixtures" / "intel_types.json"


def map_fixture_path() -> Path:
    return Path(settings.BASE_DIR) / "intel" / "fixtures" / "intel_map.json"


def _load(path: Path, empty: dict) -> dict:
    if not path.exists():
        logger.info("No intel fixture at %s", path)
        return empty
    try:
        with path.open() as handle:
            return json.load(handle)
    except (OSError, ValueError):
        logger.exception("Could not read intel fixture %s", path)
        return empty


@lru_cache(maxsize=1)
def load_types() -> dict[int, tuple[str, str, int]]:
    """``type_id -> (type name, group name, category id)``."""
    data = _load(types_fixture_path(), {"types": {}})
    return {
        int(type_id): (row[0], row[1], int(row[2]))
        for type_id, row in data.get("types", {}).items()
    }


@lru_cache(maxsize=1)
def load_map() -> dict:
    """``{"systems": {id: name}, "edges": {id: [neighbour ids]}}``."""
    return _load(map_fixture_path(), {"systems": {}, "edges": {}})


@lru_cache(maxsize=1)
def system_ids_by_name() -> dict[str, int]:
    return {
        name.lower(): int(system_id)
        for system_id, name in load_map().get("systems", {}).items()
    }
