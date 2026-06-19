"""Feed app constants — faction IDs, thresholds, R2Z2 settings."""

from __future__ import annotations

# Faction warfare militia factions
FACTION_AMARR = 500001
FACTION_MINMATAR = 500002
MILITIA_FACTION_IDS = frozenset({FACTION_AMARR, FACTION_MINMATAR})

# Amarr–Minmatar warzone regions (ESI region_id)
FW_WARZONE_REGIONS: dict[int, str] = {
    10000036: "Devoid",
    10000038: "The Bleak Lands",
    10000030: "Heimatar",
    10000042: "Metropolis",
}

# R2Z2
R2Z2_BASE_URL = "https://r2z2.zkillboard.com/ephemeral"
R2Z2_SEQUENCE_URL = f"{R2Z2_BASE_URL}/sequence.json"
R2Z2_USER_AGENT = (
    "minmatar.org-feed/1.0 (https://minmatar.org; activity feed ingestion)"
)
R2Z2_SUCCESS_SLEEP_MS = 100
R2Z2_NOT_FOUND_SLEEP_MS = 6000
R2Z2_POLL_SOFT_TIME_LIMIT_SECONDS = 25

# Retention
FEED_KILLMAIL_RETENTION_DAYS = 30

# API defaults
FEED_DEFAULT_HISTORY_DAYS = 7
FEED_MAX_HISTORY_DAYS = 30
FEED_DEFAULT_PAGE_LIMIT = 30

# Rollup defaults (override via FeedRollupConfig)
DEFAULT_ROLLUP_CONFIG: dict[str, dict] = {
    "kill_burst": {
        "window_minutes": 15,
        "min_kills": 8,
    },
    "fleet_active": {
        "window_minutes": 20,
        "min_kills": 5,
        "min_pilots": 8,
        "stale_minutes": 20,
        "dominant_faction_threshold": 0.4,
    },
    "militia_joins": {
        "hourly_min_count": 5,
        "daily_min_count": 15,
        "hourly_window_hours": 1,
        "daily_window_hours": 24,
    },
}

ROLLUP_VERSIONS: dict[str, int] = {
    "kill_burst": 1,
    "fleet_active": 1,
    "militia_joins": 1,
    "communication": 1,
}
