"""
Every tunable rule of the capability engine, in one place.

Bump RULES_VERSION whenever a value here changes: the nightly job sees the
mismatch and recomputes every fitting. The rule IDs (R1...) match
docs/capabilities/capability-engine-design.md.
"""

RULES_VERSION = 1

# R8: core floor is this mastery level (I..V).
CORE_MASTERY_LEVEL = 3
# R8: hull bonus (trait) skills get at least this core level.
TRAIT_CORE_LEVEL = 3
# R11: optimal is this mastery level.
OPTIMAL_MASTERY_LEVEL = 5
# R11: dogma-only skills reach optimal V when they give this much per level.
OPTIMAL_MIN_BONUS = 2.0

# R9: the empirical raise. Pilots with this many fleets in the hull who
# meet the fit's hard requirements; raise core to the level this share of
# them already has (0.1 = the level 90% have). Capped at mastery V.
PROVEN_MIN_FLEETS = 3
EMPIRICAL_MIN_PILOTS = 8
EMPIRICAL_QUANTILE = 0.1

# R12: flag a core row for the doctrine team when fewer Proven pilots meet it.
OVER_ASK_FLAG_SHARE = 0.7

# Recompute a fitting at least this often even when its inputs are the
# same: the empirical levels move as Proven pilots train.
REQUIREMENTS_MAX_AGE_DAYS = 7

# Proven: distinct fleets in the capability over this many days.
PROVEN_WINDOW_DAYS = 365

# R15: no attribute sync; a flat estimate.
SP_PER_HOUR = 2250
# R14: training-day floor so level-I skills don't always rank first.
MIN_TRAIN_DAYS = 1.0

CAPABILITIES = (
    "DPS",
    "Logistics",
    "Links",
    "Support",
    "Tackle",
    "Recon",
    "Dreads",
    "Carriers",
)

# R10: which stat buckets count toward core for each capability.
CORE_BUCKETS = {
    "DPS": {
        "damage",
        "tank",
        "capacitor",
        "navigation",
        "targeting",
        "fitting",
        "drones",
    },
    "Logistics": {
        "support",
        "tank",
        "capacitor",
        "navigation",
        "targeting",
        "fitting",
    },
    "Links": {"support", "tank", "capacitor", "navigation", "fitting"},
    "Support": {
        "support",
        "tank",
        "capacitor",
        "navigation",
        "targeting",
        "fitting",
    },
    "Tackle": {
        "support",
        "tank",
        "navigation",
        "targeting",
        "fitting",
        "capacitor",
    },
    "Recon": {"navigation", "jump", "targeting", "fitting", "support"},
    "Dreads": {
        "damage",
        "tank",
        "capacitor",
        "targeting",
        "jump",
        "fitting",
        "navigation",
    },
    "Carriers": {
        "drones",
        "tank",
        "capacitor",
        "targeting",
        "jump",
        "fitting",
        "navigation",
        "support",
    },
}

# R14: how much a bucket is worth for "train next" and the support score.
BUCKET_WEIGHTS = {
    "damage": 1.0,
    "tank": 1.0,
    "support": 1.0,
    "capacitor": 0.6,
    "navigation": 0.6,
    "targeting": 0.5,
    "jump": 0.5,
    "drones": 0.5,
    "fitting": 0.3,
}
DEFAULT_BUCKET_WEIGHT = 0.3
