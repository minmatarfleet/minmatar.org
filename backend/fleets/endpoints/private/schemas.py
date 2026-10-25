"""Schemas for fleet invites (standard and private) and ship targets."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from timezones.schemas import TimezoneTag


class WaveRequest(BaseModel):
    tribe_group_ids: List[int] = []
    corporation_ids: List[int] = []
    user_ids: List[int] = []
    # Alliance health onboarding buckets: "first_week", "more_fleets".
    onboarding: List[str] = []
    # Bracket codes the group, corporation and new pilot picks must play
    # in; "any" for no limit (Strategic FCs on strategic or private fleets
    # only). Null for the fleet's own timezones.
    timezones: Optional[List[str]] = None
    note: str = Field(default="", max_length=300)


class TargetHelp(BaseModel):
    name: str
    short: int
    own: int


class CappedPilot(BaseModel):
    """A pilot skipped because they had their fleet invite this week."""

    user_id: int
    name: str
    # The fleet whose invite counts, when it was sent, and when the pilot
    # can be invited again.
    fleet: str
    invited_at: datetime
    free_at: datetime


class TimezoneCount(BaseModel):
    code: str
    count: int


class PickCount(BaseModel):
    """A group or corporation pick: its members, and how many of them play
    in the chosen timezones."""

    kind: str
    id: int
    total: int
    in_timezone: int


class OnboardingCount(BaseModel):
    bucket: str
    total: int
    in_timezone: int


class WavePreviewResponse(BaseModel):
    picked: int
    # Group, corporation and new pilot picks who play in other timezones,
    # and how many by the bracket they play in.
    other_timezones: int = 0
    other_timezones_by_bracket: List[TimezoneCount] = []
    picks: List[PickCount] = []
    # Standard fleets: new pilots per onboarding bucket in these timezones.
    onboarding: List[OnboardingCount] = []
    already_invited: int
    new: int
    will_dm: int
    no_discord: int
    helps: List[TargetHelp]
    # Standard fleets only: skipped for Stop fleet invites / the weekly cap.
    opted_out: int = 0
    capped: int = 0
    # Who the weekly cap skips, soonest free first (at most 50).
    capped_pilots: List[CappedPilot] = []


class InvitePilot(BaseModel):
    invite_id: int
    user_id: int
    character_id: Optional[int] = None
    character_name: str
    corporation_name: Optional[str] = None
    wave: int
    # Why they were invited: first_week, more_fleets, pilot, tribe_group or
    # corporation (blank for invites made before sources were kept), and
    # the group or corporation's name.
    source_kind: str = ""
    source_name: str = ""
    answer: str
    ships: List[str]
    answered_at: Optional[datetime] = None
    # The leak trace: Strategic FCs only, null for everyone else.
    first_viewed_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    dm_delivered: Optional[bool] = None


class InviteWave(BaseModel):
    number: int
    sent_by: Optional[str] = None
    created_at: datetime
    finished_at: Optional[datetime] = None
    note: str
    labels: List[str]
    invited: int
    sent: int
    answered_in: int
    answered_out: int
    pending: int


class ShipTargetProgress(BaseModel):
    id: int
    name: str
    target: int
    have: int
    short: int
    ship_type_ids: List[int]
    group_ids: List[int]


class InviteTotals(BaseModel):
    invited: int
    answered_in: int
    characters_in: int
    answered_out: int
    pending: int


class FleetInvitesResponse(BaseModel):
    fleet_id: int
    totals: InviteTotals
    waves: List[InviteWave]
    invites: List[InvitePilot]
    targets: List[ShipTargetProgress]
    sending: bool
    reping_available_at: Optional[datetime] = None
    can_see_leak_trace: bool
    # Re-ping no answers: private fleets, Strategic FCs only.
    can_reping: bool = False
    thread_url: Optional[str] = None
    invite_only: bool = False
    # Standard fleets: new pilots not yet invited, by onboarding bucket.
    onboarding_first_week: int = 0
    onboarding_more_fleets: int = 0
    # The same, only those who play at the fleet time.
    onboarding_first_week_in_timezone: int = 0
    onboarding_more_fleets_in_timezone: int = 0
    # The brackets that play at the fleet's start time (the nearest one when
    # none does, with timezones_nearest set). Bulk picks are limited to
    # these; can_choose_timezones lets the caller pick any instead.
    fleet_timezones: List[str] = []
    timezones_nearest: bool = False
    can_choose_timezones: bool = False


class WaveSentResponse(BaseModel):
    number: int
    invited: int
    will_dm: int


class RepingResponse(BaseModel):
    pilots: int


class MyInviteResponse(BaseModel):
    invite_id: int
    answer: str


class DiscordSitOutRequest(BaseModel):
    discord_user_id: int


class StopInvitesResponse(BaseModel):
    stopped: bool


class ShipTargetLine(BaseModel):
    name: str = Field(max_length=64)
    target: int = Field(ge=1, le=999)
    ship_type_ids: List[int] = []
    group_ids: List[int] = []


class ShipTargetsRequest(BaseModel):
    lines: List[ShipTargetLine] = Field(default_factory=list, max_length=20)


class InviteCandidate(BaseModel):
    kind: str
    id: int
    name: str
    detail: str
    # Why this pick can't be invited now: "invited", "opted_out" or
    # "capped"; null when it can. "opted_out" and "capped" picks can still
    # be added; the send skips them.
    blocked: Optional[str] = None
    # "capped" only: the invite that counts this week.
    capped: Optional[CappedPilot] = None
    # Pilots: their timezones.
    timezone: Optional[TimezoneTag] = None
    # Groups and corporations: members, and how many play in the chosen
    # timezones.
    members: Optional[int] = None
    in_timezone: Optional[int] = None


class ResolveNamesRequest(BaseModel):
    """A paste of primary character names or Discord usernames."""

    text: str = Field(default="", max_length=4000)


class ResolvedPilot(BaseModel):
    kind: str
    id: int
    name: str
    detail: str
    matched_as: str
    # As on InviteCandidate.
    blocked: Optional[str] = None
    capped: Optional[CappedPilot] = None
    timezone: Optional[TimezoneTag] = None


class ResolveNamesResponse(BaseModel):
    matched: List[ResolvedPilot]
    not_found: List[str]


class SuggestedTargetLine(BaseModel):
    name: str
    ship_type_ids: List[int]


class PastTargetLine(BaseModel):
    name: str
    target: int
    ship_type_ids: List[int]
    group_ids: List[int]


class PastTargetFleet(BaseModel):
    fleet_id: int
    title: str
    start_time: datetime
    lines: List[PastTargetLine]


class TargetSuggestionsResponse(BaseModel):
    """Lines to start from: one per EVE group in the doctrine, and the
    caller's recent fleets that had targets."""

    doctrine: List[SuggestedTargetLine]
    past_fleets: List[PastTargetFleet]


class UnmatchedHull(BaseModel):
    ship_type_id: int
    ship_name: str
    characters: int


class TargetLineOwner(BaseModel):
    user_id: int
    character_id: int
    character_name: str
    ship_type_id: int
    ship_name: str
    location_name: str
    at_formup: bool


class ShipLine(BaseModel):
    ship_type_id: int
    target_id: int


class CharacterHangar(BaseModel):
    character_id: int
    ship_type_ids: List[int]


class MyTargetHangarResponse(BaseModel):
    lines_by_ship: List[ShipLine]
    hangars: List[CharacterHangar]
