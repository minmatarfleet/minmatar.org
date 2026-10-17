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


class CorporationPrimeWindow(Schema):
    zone: str
    start_hour: int
    end_hour: int
    pilots: int = 0


class CorporationTenureBand(Schema):
    key: str
    count: int


class CorporationTenure(Schema):
    mains: int = 0
    average_days: Optional[int] = None
    bands: List[CorporationTenureBand] = []


class CorporationHomeSystem(Schema):
    name: str
    share: float


class CorporationHull(Schema):
    type_id: int
    name: str
    pilots: int


class CorporationTurnoutRecord(Schema):
    pilots: int
    date: Optional[str] = None
    title: str = ""


class CorporationMonthRecord(Schema):
    month: str
    fleets: int


class CorporationRecords(Schema):
    biggest_turnout: Optional[CorporationTurnoutRecord] = None
    busiest_month: Optional[CorporationMonthRecord] = None


class CorporationLeader(Schema):
    character_id: int
    character_name: str
    value: int


class CorporationLeaderboards(Schema):
    fleets: List[CorporationLeader] = []
    kills: List[CorporationLeader] = []
    fleets_led: List[CorporationLeader] = []


class CorporationTribeGroupCount(Schema):
    name: str
    members: int


class CorporationAbout(Schema):
    """Cached About-tab rollups; mains only, never alts."""

    founded: Optional[str] = None
    home_system: Optional[CorporationHomeSystem] = None
    # 7 rows (Monday first) x 24 EVE-time hours of people on fleets.
    heatmap: List[List[int]] = []
    prime_windows: List[CorporationPrimeWindow] = []
    tenure: Optional[CorporationTenure] = None
    founders: int = 0
    hulls: List[CorporationHull] = []
    records: Optional[CorporationRecords] = None
    leaderboards: Optional[CorporationLeaderboards] = None
    tribe_groups: List[CorporationTribeGroupCount] = []


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
    about: Optional[CorporationAbout] = None


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
    corp_joined_at: Optional[str] = None
    last_fleet_at: Optional[str] = None
    # Per person (alts folded, each fleet once), repeated on each character.
    person_fleets_90d: Optional[int] = None
    # Distinct fleets per week for the person, oldest first, ending now.
    weekly_fleets: List[int] = []
    top_hull_id: Optional[int] = None
    top_hull_name: Optional[str] = None
    tribe_groups: List[str] = []
    status_history: List["CorporationMemberStatusChange"] = []
    # From the latest alliance health snapshot's trial review.
    trial_ready: bool = False
    trial_reason: Optional[str] = None
    # Set when the viewer may not see which characters belong to this person:
    # the row stands for the person and the rest are only counted.
    characters_hidden: bool = False
    hidden_character_count: int = 0


class CorporationMemberStatusChange(Schema):
    to_status: str
    changed_at: str


CorporationMemberDetails.model_rebuild()


class CorporationMemberAccess(Schema):
    can_view_members: bool
    can_view_characters: bool
    # CEO only: the corporation page's Settings tab.
    can_edit_settings: bool = False
    # Projects tab: corp leadership sees it; CEO and directors attach.
    can_view_projects: bool = False
    can_manage_projects: bool = False


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


class CorporationProjectTarget(Schema):
    # The configuration key: locations, ships, factions, identities ...
    kind: str
    names: List[str]


class CorporationProjectContributor(Schema):
    character_id: int
    character_name: str
    contributed: int


class CorporationProjectCampaign(Schema):
    slug: str
    name: str
    status: str


class CorporationProject(Schema):
    project_id: str
    corporation_id: int
    corporation_name: str
    name: str
    description: str = ""
    state: str
    kind: str = ""
    targets: List[CorporationProjectTarget] = []
    creator_id: Optional[int] = None
    creator_name: str = ""
    progress_current: int = 0
    progress_desired: int = 0
    reward_initial: Optional[float] = None
    reward_remaining: Optional[float] = None
    reward_per_contribution: Optional[float] = None
    participation_limit: Optional[int] = None
    created: Optional[datetime] = None
    expires: Optional[datetime] = None
    finished: Optional[datetime] = None
    last_modified: datetime
    contributors: List[CorporationProjectContributor] = []
    campaigns: List[CorporationProjectCampaign] = []


class CorporationProjectsResponse(Schema):
    corporation_id: int
    # CEO or director: may put a project toward a campaign.
    can_manage: bool
    # A CEO or director token with esi-corporations.read_projects.v1.
    has_token: bool
    synced_at: Optional[datetime] = None
    refreshing: bool = False
    projects: List[CorporationProject]
    # Scheduled and active campaigns a project can be put toward.
    campaigns: List[CorporationProjectCampaign]
