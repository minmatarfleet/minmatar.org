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
    "engagement_copy": {
        "tiers": [
            {
                "code": "small",
                "min_kills": 8,
                "min_pilots": 6,
                "generic_title": "Small skirmish in {system}",
                "militia_title": "{faction} patrol clash",
                "preview": "Light contact on the front.",
                "previews": {
                    "generic": "Brief exchange — {ships}.",
                    "militia": "Militia pilots trading blows — {ships}.",
                },
            },
            {
                "code": "medium",
                "min_kills": 14,
                "min_pilots": 12,
                "generic_title": "Medium skirmish in {system}",
                "militia_title": "{faction} skirmish",
                "preview": "Sustained fighting reported.",
                "previews": {
                    "generic": "Skirmish escalating — {ships}.",
                    "militia": "Enlisted pilots holding the line — {ships}.",
                },
            },
            {
                "code": "large",
                "min_kills": 22,
                "min_pilots": 18,
                "generic_title": "Large skirmish in {system}",
                "militia_title": "{faction} fleet engagement",
                "preview": "Heavy fighting across multiple hull types.",
                "previews": {
                    "generic": "Large skirmish brewing — {ships}.",
                    "militia": "Organized militia presence — {ships}.",
                },
            },
            {
                "code": "heavy",
                "min_kills": 35,
                "min_pilots": 28,
                "generic_title": "Heavy engagement in {system}",
                "militia_title": "Large {faction} fleet fight",
                "preview": "Major fight with broad ship losses.",
                "previews": {
                    "generic": "Heavy engagement underway — {ships}.",
                    "militia": "Large organized militia fight — {ships}.",
                },
            },
            {
                "code": "major",
                "min_kills": 50,
                "min_pilots": 40,
                "generic_title": "Major engagement in {system}",
                "militia_title": "Major {faction} operation",
                "preview": "Significant battle on the warzone front.",
                "previews": {
                    "generic": "Major engagement — {ships} among the losses.",
                    "militia": "Major militia operation — {ships}.",
                },
                "militia_active_preview": "Major militia operation underway on the front.",
            },
        ],
    },
    "fleet_active": {
        "window_minutes": 20,
        "min_kills": 5,
        "min_pilots": 6,
        "stale_minutes": 20,
        "dominant_faction_threshold": 0.75,
    },
    "militia_joins": {
        "hourly_min_count": 5,
        "daily_min_count": 15,
        "hourly_window_hours": 1,
        "daily_window_hours": 24,
    },
    "affiliation_sync": {
        "populate_batch_size": 200,
        "refresh_batch_size": 150,
        "refresh_stale_hours": 168,
        "esi_affiliation_chunk_size": 1000,
    },
}

ROLLUP_VERSIONS: dict[str, int] = {
    "kill_burst": 2,
    "fleet_active": 2,
    "militia_joins": 1,
}
