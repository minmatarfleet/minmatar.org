"""Shared response/request schemas for corporation endpoints."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from ninja import Schema


class CorporationType(str, Enum):
    ALLIANCE = "alliance"
    ASSOCIATE = "associate"
    MILITIA = "militia"
    PUBLIC = "public"


class CorporationMemberResponse(Schema):
    character_id: int
    character_name: str
    primary_character_id: Optional[int] = None
    primary_character_name: Optional[str] = None
    registered: bool = False
    exempt: bool = False


class CorporationRoleCharacterResponse(Schema):
    character_id: int
    character_name: str


class CorporationLeadershipResponse(Schema):
    character_id: int
    character_name: str
    role: str
    prime_time: Optional[str] = None
    observed_prime_times: List[str] = []


class TimezoneBucketCount(Schema):
    bucket: str
    declared: int = 0
    observed: int = 0


class WeekdayCount(Schema):
    day: int
    members: int = 0
    kills: int = 0


class CorporationMediaResponse(Schema):
    id: int
    sort_order: int
    kind: str
    url: Optional[str] = None
    post_id: Optional[int] = None
    caption: str = ""
    youtube_id: Optional[str] = None


class CorporationCeoResponse(Schema):
    character_id: int
    character_name: str


class CorporationResponse(Schema):
    corporation_id: int
    corporation_name: str
    alliance_id: Optional[int] = None
    alliance_name: Optional[str] = None
    faction_id: Optional[int] = None
    faction_name: Optional[str] = None
    type: CorporationType
    introduction: Optional[str] = None
    biography: Optional[str] = None
    executor_notes: Optional[str] = None
    timezones: Optional[List[str]] = None
    requirements: Optional[List[str]] = None
    members: List[CorporationMemberResponse] = []
    directors: List[CorporationRoleCharacterResponse] = []
    recruiters: List[CorporationRoleCharacterResponse] = []
    stewards: List[CorporationRoleCharacterResponse] = []
    active: bool
    trial: bool = False
    ticker: Optional[str] = None
    member_count: Optional[int] = None
    human_count: Optional[int] = None
    ceo: Optional[CorporationCeoResponse] = None
    leadership: List[CorporationLeadershipResponse] = []
    timezone_distribution: List[TimezoneBucketCount] = []
    weekday_distribution: List[WeekdayCount] = []
    highlights: Optional[str] = None
    activity_summary: Optional[str] = None
    media: List[CorporationMediaResponse] = []
    discord_invite_url: Optional[str] = None


class CorporationSummarySlice(Schema):
    key: str
    count: int


class CorporationCommunitySummary(Schema):
    humans: int = 0
    slices: List[CorporationSummarySlice] = []


class CorporationFleetParticipationSummary(Schema):
    fleet_instances: int = 0
    humans: int = 0
    slices: List[CorporationSummarySlice] = []


class CorporationShipSlice(Schema):
    key: str
    count: float


class CorporationFleetShipSummary(Schema):
    pilot_fleets: int = 0
    slices: List[CorporationShipSlice] = []


class CorporationKillSummary(Schema):
    killmails: int = 0
    slices: List[CorporationSummarySlice] = []


class CorporationPublicSummary(Schema):
    window_days: int = 90
    community: CorporationCommunitySummary
    fleet_participation: CorporationFleetParticipationSummary
    fleet_ships: CorporationFleetShipSummary
    kills: CorporationKillSummary


class CorporationSlugResponse(Schema):
    corporation_id: int
    slug: str


class CorporationInfoResponse(Schema):
    corporation_id: int
    corporation_name: str
    alliance_id: Optional[int] = None
    alliance_name: Optional[str] = None
    faction_id: Optional[int] = None
    faction_name: Optional[str] = None
    type: CorporationType
    introduction: Optional[str] = None
    biography: Optional[str] = None
    timezones: Optional[List[str]] = None
    requirements: Optional[List[str]] = None
    active: bool
    trial: bool = False
    ticker: Optional[str] = None
    member_count: Optional[int] = None
    human_count: Optional[int] = None
    ceo: Optional[CorporationCeoResponse] = None
    leadership: List[CorporationLeadershipResponse] = []
    timezone_distribution: List[TimezoneBucketCount] = []
    weekday_distribution: List[WeekdayCount] = []
    highlights: Optional[str] = None
    activity_summary: Optional[str] = None
    media: List[CorporationMediaResponse] = []
    discord_invite_url: Optional[str] = None
    public_summary: Optional[CorporationPublicSummary] = None
    application_process: Optional["CorporationApplicationProcess"] = None


class CorporationApplicationProcess(Schema):
    outstanding: int = 0
    applications_per_month: Optional[float] = None
    acceptance_days: Optional[float] = None
    average_skill_points: Optional[int] = None


class CorporationOpenApplication(Schema):
    application_id: int
    character_id: Optional[int] = None
    character_name: str
    created_at: datetime


class CorporationMemberDetails(Schema):
    character_id: int
    character_name: str
    user_name: Optional[str] = None
    primary_character_id: Optional[int] = None
    primary_character_name: Optional[str] = None
    registered: bool = False
    exempt: bool = False
    esi_suspended: bool = False
    token_count: int = 0
    token_level: str = None
    fleets_90d: int = 0
    kills_90d: int = 0
    voice_hours_90d: float = 0
    prime_time: Optional[str] = None
    observed_prime_times: List[str] = []
    community_status: Optional[str] = None
    # Set when the viewer may not see which characters belong to this person:
    # the row stands for the person and the rest are only counted.
    characters_hidden: bool = False
    hidden_character_count: int = 0


class CorporationMemberAccess(Schema):
    can_view_members: bool
    can_view_characters: bool
    # CEO only: the corporation page's Settings tab.
    can_edit_settings: bool = False


class CorporationMembersTopResponse(Schema):
    metric: str
    members: List[CorporationMemberDetails]


class CorporationAdminResponse(Schema):
    corporation_id: int
    executor_notes: Optional[str] = None
    discord_bot_present: bool = False
    discord_guild_name: Optional[str] = None
    discord_invite_url: Optional[str] = None
    bot_invite_url: Optional[str] = None
    humans: Optional[int] = None
    active_90d: Optional[int] = None
    active_90d_pct: Optional[float] = None
    growth_90d_pct: Optional[float] = None
    stewards: List[CorporationRoleCharacterResponse] = []
    leadership_missing_prime_time: List[CorporationLeadershipResponse] = []
