"""Response and request shapes for the campaigns API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from ninja import Schema
from pydantic import Field


class CampaignSystemSummary(Schema):
    id: int
    name: str
    solar_system_id: int
    role: str
    goal: str
    priority: str = "medium"
    is_fw_objective: bool = True
    contested_percent: float | None = None
    contested_change_24h: float | None = None
    victory_points: int | None = None
    victory_points_threshold: int | None = None
    operational_state: str = "unknown"
    contested_updated_at: datetime | None = None
    advantage_updated_at: datetime | None = None
    occupier_faction_id: int | None = None
    owner_faction_id: int | None = None
    advantage_basis: str = "unknown"
    advantage_source: str = "pilot"
    advantage_our_pct: float | None = None
    advantage_enemy_pct: float | None = None
    advantage_net_pct: float | None = None
    advantage_age_minutes: int | None = None
    advantage_is_stale: bool = True
    kills_24h: int = 0
    losses_24h: int = 0
    kills_change_24h: int = 0
    trend: list[dict] = []
    status_chip: str = "holding"


class CampaignAreaOut(Schema):
    id: int
    scope: str
    name: str
    constellation_id: int | None = None
    region_id: int | None = None


class CampaignOpponentOut(Schema):
    id: int
    name: str
    ticker: str = ""
    alliance_id: int | None = None
    corporation_id: int | None = None
    faction_id: int | None = None


class CampaignFittingOut(Schema):
    id: int
    fitting_id: int
    name: str
    ship_name: str = ""
    role_label: str = ""
    srp_eligible: bool = True
    order: int = 0


class CampaignStructureOut(Schema):
    id: int
    name: str
    structure_type: str
    type_id: int | None = None
    solar_system_id: int
    system_name: str
    corporation_id: int | None = None
    corporation_name: str = ""
    alliance_id: int | None = None
    alliance_name: str = ""
    related_alliance_id: int | None = None
    related_alliance_name: str = ""
    status: str
    source: str
    fitting: str = ""
    reinforce_hour: int | None = None
    timer_id: int | None = None
    timer_at: datetime | None = None
    destroyed_at: datetime | None = None
    killmail_id: int | None = None


class CampaignListItem(Schema):
    id: int
    slug: str
    name: str
    short_code: str
    tagline: str = ""
    kind: str = "faction_warfare"
    status: str
    start_at: datetime
    end_at: datetime
    cover_image_url: str = ""
    systems: list[CampaignSystemSummary] = []
    areas: list[CampaignAreaOut] = []
    opponents: list[CampaignOpponentOut] = []
    structures_remaining: int = 0
    structures_destroyed: int = 0
    next_timer_at: datetime | None = None
    enlisted: int = 0
    kills: int = 0
    isk_destroyed: int = 0
    is_enlisted: bool = False


class CampaignTotals(Schema):
    enlisted: int = 0
    kills: int = 0
    losses: int = 0
    isk_destroyed: int = 0
    isk_lost: int = 0
    complexes: int = 0
    advantage_sites: int = 0
    advantage_generated: float = 0
    structure_kills: int = 0
    capital_kills: int = 0
    structures_destroyed: int = 0
    structures_remaining: int = 0
    active_today: int = 0


class CampaignDetail(Schema):
    id: int
    slug: str
    name: str
    short_code: str
    tagline: str = ""
    description_md: str = ""
    cover_image_url: str = ""
    kind: str = "faction_warfare"
    status: str
    start_at: datetime
    end_at: datetime
    commander_order_text: str = ""
    commander_order_is_draft: bool = True
    systems: list[CampaignSystemSummary] = []
    areas: list[CampaignAreaOut] = []
    opponents: list[CampaignOpponentOut] = []
    structures: list[CampaignStructureOut] = []
    fittings: list[CampaignFittingOut] = []
    totals: CampaignTotals
    is_enlisted: bool = False
    my_points: int = 0
    my_rank: int | None = None
    my_streak: int = 0
    characters_included: int = 0
    characters_tracked: int = 0
    standing_fleet_up: bool = False
    standing_fleet_members: int = 0
    standing_fleet_boss: str | None = None


class RightNow(Schema):
    active_pilots: int = 0
    system_heat: int = 0
    hostile_gangs: list[dict] = []
    standing_fleet_up: bool = False
    standing_fleet_members: int = 0
    standing_fleet_boss: str | None = None
    gangs_forming: list[dict] = []
    my_streak: int = 0
    my_orders_done: int = 0
    my_orders_total: int = 0
    ticker: list[dict] = []


class WeekTargetOut(Schema):
    id: int
    system: str
    system_id: int
    goal: str
    metric: str
    target: float
    progress: float
    pace_expected: float
    baseline: float = 0
    pace: str
    proposed: bool
    last_week_actual: float = 0
    days_under_line: int = 0
    projected_arc_date: date | None = None
    # The viewer's own contribution to this target this week.
    my_complexes: int = 0
    my_advantage_sites: int = 0
    my_readings: int = 0
    my_structures_reported: int = 0


class WeekPlan(Schema):
    week_start: date
    week_end: date | None = None
    week_index: int = 1
    week_count: int = 1
    day_index: int = 1
    targets: list[WeekTargetOut] = []
    commander_order_text: str = ""
    summary: dict = {}


class CampaignFleetOut(Schema):
    """One fleet attributed to the campaign and what it did."""

    id: int
    type: str
    description: str = ""
    objective: str = ""
    start_time: datetime | None = None
    status: str = "unknown"
    fleet_commander: str | None = None
    fleet_commander_id: int | None = None
    doctrine: str | None = None
    aar_link: str | None = None
    is_live: bool = False
    pilots: int = 0
    kills: int = 0
    losses: int = 0
    isk_destroyed: int = 0


class OrderOut(Schema):
    id: int
    kind: str
    label: str
    params: dict = {}
    points: int
    system: str | None = None
    gap_share_pct: float = 0
    progress: float = 0
    completed: bool = False


class LeaderboardRow(Schema):
    rank: int
    user_id: int
    username: str
    character_id: int | None = None
    character_name: str = ""
    value: float
    points: int


class KillmailOut(Schema):
    killmail_id: int
    killmail_time: datetime
    outcome: str
    solar_system_id: int
    victim_character_name: str = ""
    victim_character_id: int | None = None
    victim_corporation_id: int | None = None
    victim_alliance_id: int | None = None
    victim_faction_id: int | None = None
    victim_ship_type_id: int | None = None
    killer_character_id: int | None = None
    killer_character_name: str = ""
    killer_faction_id: int | None = None
    isk_value: int = 0
    enlisted_attacker_count: int = 0
    is_solo: bool = False
    is_structure: bool = False
    is_capital: bool = False
    structure_id: int | None = None


class SiteOut(Schema):
    id: int
    occurred_at: datetime
    site_kind: str
    amount_lp: int
    system: str
    username: str | None = None
    character_id: int | None = None
    character_name: str = ""
    plex_class: str = ""
    # Scout / Small / Medium / Large / Open, without the NVY-5 variant noise.
    plex_size: str = ""
    confidence: str = ""


class AwardOut(Schema):
    code: str
    label: str
    scope: str
    week_start: date | None = None
    awarded_at: datetime
    username: str
    value: float | None = None
    metric: str = ""


class TimelineEvent(Schema):
    id: int
    kind: str
    occurred_at: datetime
    title: str
    body: str = ""
    side: str = "neutral"
    source: str = "campaign"
    system: str | None = None
    is_active: bool = False


class RosterRow(Schema):
    user_id: int
    username: str
    primary_character: str = ""
    character_id: int | None = None
    corporation_id: int | None = None
    corporation_name: str = ""
    prime_time: str = ""
    observed_prime_time: str = ""
    last_active_day: date | None = None
    streak_days: int = 0
    points: int = 0
    characters_included: int = 0
    characters_tracked: int = 0


class Roster(Schema):
    pilots: list[RosterRow] = []
    coverage: list[dict] = []
    by_prime_time: dict = {}


class CharacterReadiness(Schema):
    character_id: int
    character_name: str
    corporation_id: int | None = None
    is_primary: bool = False
    token_type: str = ""
    counts_for: str = ""
    state: str = "missing"
    included: bool = True
    action_url: str = ""


class ReadinessOut(Schema):
    characters: list[CharacterReadiness] = []
    tracked: int = 0
    total: int = 0


class EnlistRequest(Schema):
    source: Literal["fleet_prompt", "gang_ping", "web", "admin"] = "web"
    notify_gang_forming: bool = True
    notify_standing_fleet: bool = True
    notify_activity_nearby: bool = False
    notify_streak_at_risk: bool = True
    digest_hour: int = Field(default=18, ge=0, le=23)


class EnlistResponse(Schema):
    enlisted: bool
    characters_included: int = 0
    characters_missing_scopes: list[str] = []
    token_chain_url: str = ""


class AdvantageRequest(Schema):
    our_pct: float = Field(ge=0, le=100)
    enemy_pct: float = Field(ge=0, le=100)


class AdvantageResponse(Schema):
    accepted: bool
    status: str
    our_pct: float | None = None
    enemy_pct: float | None = None
    net_pct: float | None = None
    points: int = 0


class GangRequest(Schema):
    # These land in a CampaignEvent title and body, both of which are bounded
    # columns, so they are bounded here rather than at the database.
    ships: str = Field(min_length=1, max_length=120)
    solar_system_id: int | None = None
    note: str = Field(default="", max_length=280)
    voice_channel_id: int | None = None


class CampaignCreateRequest(Schema):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=64)
    short_code: str = Field(pattern=r"^[A-Za-z0-9]{2,12}$")
    kind: Literal["faction_warfare", "strategic"] = "faction_warfare"
    tagline: str = Field(default="", max_length=200)
    description_md: str = ""
    start_at: datetime
    end_at: datetime
    system_ids: list[int] = []


class CampaignSystemPatch(Schema):
    is_fw_objective: bool | None = None
    goal: str | None = None
    role: str | None = None
    priority: str | None = None


class CampaignAreaCreateRequest(Schema):
    scope: Literal["constellation", "region"]
    name: str = Field(min_length=1, max_length=128)
    constellation_id: int | None = None
    region_id: int | None = None


class CampaignCreated(Schema):
    slug: str
    short_code: str
    name: str
    kind: str
    status: str
    systems: list[str] = []


class StructureAttachRequest(Schema):
    name: str = Field(min_length=1, max_length=255)
    structure_type: str = Field(min_length=1, max_length=64)
    system_name: str = Field(min_length=1, max_length=128)
    solar_system_id: int | None = None
    corporation_name: str = Field(default="", max_length=255)
    corporation_id: int | None = None
    alliance_name: str = Field(default="", max_length=255)
    alliance_id: int | None = None
    related_alliance_name: str = Field(default="", max_length=255)
    related_alliance_id: int | None = None
    selected_item_window: str = ""
    fitting: str = ""
    reinforce_hour: int | None = None
    # Optional live timer created alongside the recon row.
    timer_at: datetime | None = None
    timer_state: str | None = None


class OpponentAttachRequest(Schema):
    name: str = Field(min_length=1, max_length=255)
    ticker: str = Field(default="", max_length=16)
    alliance_id: int | None = None
    corporation_id: int | None = None
    faction_id: int | None = None


class TimerAttachRequest(Schema):
    timer_id: int


class CommanderOrderRequest(Schema):
    text: str = Field(max_length=280)


class WeekTargetPatch(Schema):
    target: float
    accept: bool = True
