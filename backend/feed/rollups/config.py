from __future__ import annotations

from typing import Any

from feed.constants import DEFAULT_ROLLUP_CONFIG, ROLLUP_VERSIONS
from feed.models import FeedRollupConfig


def get_rollup_config(rollup_code: str) -> dict[str, Any]:
    defaults = DEFAULT_ROLLUP_CONFIG.get(rollup_code, {})
    try:
        row = FeedRollupConfig.objects.get(rollup_code=rollup_code)
        if row.is_enabled and row.config:
            return {**defaults, **row.config}
    except FeedRollupConfig.DoesNotExist:
        pass
    return defaults


def get_rollup_version(rollup_code: str) -> int:
    try:
        row = FeedRollupConfig.objects.get(rollup_code=rollup_code)
        return row.version
    except FeedRollupConfig.DoesNotExist:
        return ROLLUP_VERSIONS.get(rollup_code, 1)
