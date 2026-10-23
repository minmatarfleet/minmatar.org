"""Schemas for private fleet invites and ship targets."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class WaveRequest(BaseModel):
    tribe_group_ids: List[int] = []
    corporation_ids: List[int] = []
    user_ids: List[int] = []
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


class InvitePilot(BaseModel):
    invite_id: int
    user_id: int
    character_id: Optional[int] = None
    character_name: str
    corporation_name: Optional[str] = None
    wave: int
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
