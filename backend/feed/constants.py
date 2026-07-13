"""Feed app constants — faction IDs, thresholds, R2Z2 settings."""

from __future__ import annotations

# ESI empire faction IDs (killmails, affiliations, fw/systems)
FACTION_CALDARI = 500001
FACTION_MINMATAR = 500002
FACTION_AMARR = 500003
FACTION_GALLENTE = 500004
MILITIA_FACTION_IDS = frozenset({FACTION_AMARR, FACTION_MINMATAR})

# Amarr–Minmatar warzone regions (ESI region_id)
FW_WARZONE_REGIONS: dict[int, str] = {
    10000036: "Devoid",
    10000038: "The Bleak Lands",
    10000030: "Heimatar",
    10000042: "Metropolis",
}

# R2Z2 — https://github.com/zKillboard/zKillboard/wiki/API-(R2Z2)
# Live edge: sleep >= 6s after 404 (avg ~1 killmail / 5.5s). Catch-up: 100ms
# between 200s (<= 10/s; limit is 15/s per IP). Rate-limit violators are
# banned for 1 hour (403); transient overload may return 429.
R2Z2_BASE_URL = "https://r2z2.zkillboard.com/ephemeral"
R2Z2_SEQUENCE_URL = f"{R2Z2_BASE_URL}/sequence.json"
R2Z2_USER_AGENT = (
    "minmatar.org-feed/1.0 (https://minmatar.org; activity feed ingestion)"
)
R2Z2_SUCCESS_SLEEP_MS = 100
R2Z2_NOT_FOUND_SLEEP_MS = 6000
R2Z2_RATE_LIMIT_SLEEP_SECONDS = 3600
R2Z2_BANNED_SLEEP_SECONDS = 3600
R2Z2_POLL_SOFT_TIME_LIMIT_SECONDS = 25

# Retention
FEED_KILLMAIL_RETENTION_DAYS = 30
FEED_CONTESTED_SNAPSHOT_RETENTION_DAYS = 8

# ESI faction warfare
ESI_FW_SYSTEMS_URL = "https://esi.evetech.net/latest/fw/systems/"
FEED_FW_ESI_USER_AGENT = (
    "minmatar.org-feed/1.0 (https://minmatar.org; fw contested polling)"
)

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
                "militia_size": "Small",
                "generic_title": "Small skirmish in {system}",
                "militia_title": "{size} {faction} {formation} active",
                "preview": "Light contact on the front.",
            },
            {
                "code": "medium",
                "min_kills": 14,
                "min_pilots": 12,
                "militia_size": "Medium",
                "generic_title": "Medium skirmish in {system}",
                "militia_title": "{size} {faction} {formation} active",
                "preview": "Sustained fighting reported.",
            },
            {
                "code": "large",
                "min_kills": 22,
                "min_pilots": 18,
                "militia_size": "Large",
                "generic_title": "Large skirmish in {system}",
                "militia_title": "{size} {faction} {formation} active",
                "preview": "Heavy fighting across multiple hull types.",
            },
            {
                "code": "heavy",
                "min_kills": 35,
                "min_pilots": 28,
                "militia_size": "Heavy",
                "generic_title": "Heavy engagement in {system}",
                "militia_title": "{size} {faction} {formation} active",
                "preview": "Major fight with broad ship losses.",
            },
            {
                "code": "major",
                "min_kills": 50,
                "min_pilots": 40,
                "militia_size": "Major",
                "generic_title": "Major engagement in {system}",
                "militia_title": "{size} {faction} {formation} active",
                "preview": "Significant battle on the warzone front.",
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
    "contested_change": {
        "min_delta_percent": 5.0,
        "max_events_per_poll": 15,
        "window_hours": 1,
    },
    "affiliation_sync": {
        "populate_batch_size": 200,
        "refresh_batch_size": 150,
        "refresh_stale_hours": 168,
        "esi_affiliation_chunk_size": 1000,
    },
}

ROLLUP_VERSIONS: dict[str, int] = {
    "kill_burst": 6,
    "fleet_active": 9,
    "contested_change": 1,
}

# Capital kill Discord pings (radius from Amamake)
AMAMAKE_SOLAR_SYSTEM_ID = 30002537
CAPITAL_PING_MAX_LIGHT_YEARS = 8.0
METERS_PER_LIGHT_YEAR = 9_460_528_400_000_000
CAPITAL_SHIP_GROUPS = frozenset(
    {
        "Capital Ship",
        "Dreadnought",
        "Carrier",
        "Supercarrier",
        "Titan",
        "Force Auxiliary",
    }
)
