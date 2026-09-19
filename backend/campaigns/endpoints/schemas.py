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
    contested_percent: float | None = None
    contested_change_24h: float | None = None
    victory_points: int | None = None
    victory_points_threshold: int | None = None
    operational_state: str = "unknown"
    owner_faction_id: int | None = None
    advantage_basis: str = "unknown"
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


class CampaignListItem(Schema):
    slug: str
    name: str
    short_code: str
    tagline: str = ""
    status: str
    start_at: datetime
    end_at: datetime
    cover_image_url: str = ""
    systems: list[CampaignSystemSummary] = []
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
    active_today: int = 0


class CampaignDetail(Schema):
    slug: str
    name: str
    short_code: str
    tagline: str = ""
    description_md: str = ""
    cover_image_url: str = ""
    status: str
    start_at: datetime
    end_at: datetime
    commander_order_text: str = ""
    commander_order_is_draft: bool = True
    systems: list[CampaignSystemSummary] = []
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
    pace: str
    proposed: bool
    last_week_actual: float = 0
    days_under_line: int = 0
    projected_arc_date: date | None = None


class WeekPlan(Schema):
    week_start: date
    targets: list[WeekTargetOut] = []
    commander_order_text: str = ""
    summary: dict = {}


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
    value: float
    points: int


class KillmailOut(Schema):
    killmail_id: int
    killmail_time: datetime
    outcome: str
    solar_system_id: int
    victim_character_name: str = ""
    victim_ship_type_id: int | None = None
    isk_value: int = 0
    enlisted_attacker_count: int = 0
    is_solo: bool = False


class SiteOut(Schema):
    id: int
    occurred_at: datetime
    site_kind: str
    amount_lp: int
    system: str
    username: str | None = None
    plex_class: str = ""
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
    corporation_id: int | None = None
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
    tagline: str = Field(default="", max_length=200)
    description_md: str = ""
    start_at: datetime
    end_at: datetime
    system_ids: list[int] = []


class CampaignCreated(Schema):
    slug: str
    short_code: str
    name: str
    status: str
    systems: list[str] = []


class CommanderOrderRequest(Schema):
    text: str = Field(max_length=280)


class WeekTargetPatch(Schema):
    target: float
    accept: bool = True
