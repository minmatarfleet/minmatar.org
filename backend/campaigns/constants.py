"""Tuning constants for campaign scoring and site inference."""

from __future__ import annotations

# --- Complex LP base tiers -------------------------------------------------
# Base LP by complex class before the system multiplier, contested factor and
# insurgency suppression are applied. Several classes collide on the same
# base, which is why inference reports a candidate set rather than one name.
COMPLEX_BASE_TIERS: dict[int, tuple[str, ...]] = {
    10_000: ("Scout NVY-1",),
    12_500: ("Scout NVY-5",),
    15_000: ("Small NVY-1",),
    17_500: ("Small ADV-1",),
    18_750: ("Small NVY-5",),
    20_000: ("Small ADV-5", "Medium NVY-1"),
    25_000: ("Medium NVY-5", "Medium ADV-1", "Large NVY-1", "Large ADV-1"),
    30_000: ("Medium ADV-5", "Large NVY-5", "Large ADV-5", "Open"),
    45_000: ("FRF ELT-5",),
}

# Operational state multiplier on complex LP.
OPERATIONAL_STATE_MULTIPLIER = {
    "frontline": 1.5,
    "command_operations": 1.0,
    "rearguard": 0.01,
    "unknown": 1.0,
}

# Insurgency suppression stages 2-5 raise FW LP payouts.
SUPPRESSION_MULTIPLIER = {0: 1.0, 1: 1.0, 2: 1.05, 3: 1.10, 4: 1.15, 5: 1.20}

# How close an implied base has to sit to a tier to be accepted, as a ratio.
TIER_TOLERANCE = 0.04

# Flat LP amounts that identify an advantage site family member.
ADVANTAGE_SITE_LP = 10_000
SUPPLY_CACHE_LP = 15_000

# --- Event codes -----------------------------------------------------------
# Seeded from a live pull on BearThatCares, 18 Sep YC128. Everything except
# the kill payout is unconfirmed: the wording is rendered client-side from the
# code, so we cannot tell a Rendezvous Point from a beacon or an outpost yet.
# Unconfirmed codes are stored and shown but never scored.
EVENT_CODE_SEED: list[dict] = [
    {
        "event_code": 371,
        "site_kind": "complex",
        "label": "Complex capture",
        "amount_rule": "base by class x system x contested x suppression / pilots inside",
        "confirmed": True,
        "notes": "Three captures observed in Dal, all resolving to Small plexes.",
    },
    {
        "event_code": 516,
        "site_kind": "advantage_site",
        "label": "Advantage site",
        "amount_rule": "10,000 flat (RP/beacon/outpost); 15,000 supply cache",
        "confirmed": False,
        "notes": (
            "50 payouts observed, 49 at 10,000 LP and one at 15,000. "
            "Rendezvous Point, Propaganda Beacon and Listening Outpost all "
            "pay 10,000, so they may or may not share this code. Probe: "
            "deploy a beacon or an outpost on a tracked character."
        ),
    },
    {
        "event_code": 359,
        "site_kind": "unknown",
        "label": "Large payout, unconfirmed",
        "amount_rule": "variable",
        "confirmed": False,
        "notes": (
            "One payout of 52,500 LP in Sosala, 27 Aug 01:02. Battlefields "
            "pay variable amounts, sometimes over 100k, so this is a "
            "candidate but is not confirmed. Probe: name a battlefield run."
        ),
    },
    {
        "event_code": 367,
        "site_kind": "kill",
        "label": "Kill payout",
        "amount_rule": "itemRefID is the killmail id",
        "confirmed": True,
        "notes": "Doubles as the independent check that we caught a kill.",
    },
]

# --- Scoring ---------------------------------------------------------------
DEFAULT_SCORING: dict = {
    "kill_base": 10,
    "kill_scale_cap": 5,  # points scale with min(1, cap / enlisted on mail)
    "final_blow_bonus": 5,
    "solo_bonus": 10,
    "fleet_kill_bonus": 5,
    "gang_kill_bonus": 5,
    "gang_fc_bonus": 2,
    "gang_size_max": 10,
    "loss_penalty": -3,
    "loss_penalty_in_fleet": -1,
    "isk_per_point": 10_000_000,
    "isk_points_cap_per_kill": 25,
    "complex_base": 15,
    "primary_system_bonus": 10,
    "advantage_site": 40,
    "supply_cache": 50,
    "battlefield": 60,
    "site_soft_cap": 8,  # sites per pilot per day at full value
    "advantage_reading": 5,
    "advantage_sweep": 15,
    "fleet_attended": 15,
    "fleet_attended_primary": 30,
    "standing_fleet_day": 15,
    "fleet_led": 40,
    "gang_led": 20,
    "active_day": 5,
    "streak_per_day": 5,
    "streak_cap": 25,
    "off_peak_multiplier": 1.25,
    "off_peak_hours": list(range(3, 14)),
    "contribution_mix_bonus": 0.20,
    "order_full_set": 50,
    "order_weekly": 100,
}

# Points added on top of complex_base, by base LP tier.
COMPLEX_TIER_POINTS = {
    10_000: 10,
    12_500: 12,
    15_000: 15,
    17_500: 18,
    18_750: 18,
    20_000: 20,
    25_000: 25,
    30_000: 30,
    45_000: 45,
}

# --- Orders ----------------------------------------------------------------
DEFAULT_ORDER_POINTS = {
    "fleet": 15,
    "standing_fleet": 20,
    "kill": 20,
    "gang_kill": 30,
    "gang": 30,
    "plex": 40,
    "plex_class": 50,
    "advantage_site": 40,
    "supply_cache": 50,
    "advantage_generated": 60,
    "advantage_report": 15,
    "first_kill": 10,
    "first_plex": 40,
    "weekly_active": 100,
}

# --- Weekly plan -----------------------------------------------------------
MOMENTUM_FACTOR = 1.2
MOMENTUM_BEST_WEEK_CAP = 1.5
MIN_WEEKLY_VP_TARGET = 3_000
DEFENSIVE_PLEX_CONTEST_THRESHOLD = 10.0
ADVANTAGE_READING_STALE_MINUTES = 180
ADVANTAGE_READING_HIDE_MINUTES = 720

# --- Awards ----------------------------------------------------------------
WEEKLY_AWARDS = [
    ("top_gun", "Top Gun", "kills"),
    ("plex_marathon", "Plex Marathon", "complexes"),
    ("pathfinder", "Pathfinder", "advantage_generated"),
    ("gang_of_the_week", "Gang of the Week", "gang_kills"),
    ("iron_wall", "Iron Wall", "fleets_attended"),
    ("saboteur", "Saboteur", "enemy_advantage_removed"),
]

CAMPAIGN_AWARDS = [
    ("warlord", "Warlord", "points"),
    ("closer", "Closer", "complexes"),
    ("ever_present", "Ever Present", "active_days"),
]
