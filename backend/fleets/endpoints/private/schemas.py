"""Schemas for fleet invites (standard and private) and ship targets."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class WaveRequest(BaseModel):
    tribe_group_ids: List[int] = []
    corporation_ids: List[int] = []
    user_ids: List[int] = []
    # Alliance health onboarding buckets: "first_week", "more_fleets".
    onboarding: List[str] = []
    note: str = Field(default="", max_length=300)


class TargetHelp(BaseModel):
    name: str
    short: int
    own: int


class WavePreviewResponse(BaseModel):
    picked: int
    already_invited: int
    new: int
    will_dm: int
    no_discord: int
    helps: List[TargetHelp]
    # Standard fleets only: skipped for Stop fleet invites / the weekly cap.
    opted_out: int = 0
    capped: int = 0


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
    thread_url: Optional[str] = None
    invite_only: bool = False
    # Standard fleets: new pilots not yet invited, by onboarding bucket.
    onboarding_first_week: int = 0
    onboarding_more_fleets: int = 0


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
    # "capped"; null when it can.
    blocked: Optional[str] = None


class ResolveNamesRequest(BaseModel):
    """A paste of primary character names or Discord usernames."""

    text: str = Field(default="", max_length=4000)


class ResolvedPilot(BaseModel):
    kind: str
    id: int
    name: str
    detail: str
    matched_as: str


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
