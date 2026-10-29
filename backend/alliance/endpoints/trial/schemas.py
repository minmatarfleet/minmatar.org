"""Response schemas for the Trial tab and the corp Members row insights."""

from datetime import datetime
from typing import Optional

from ninja import Schema


class TrialProgressResponse(Schema):
    day: Optional[int] = None
    review_day: int
    scale_days: int
    # Average days from trial to active, for the corp (or the alliance when
    # the corp has too few finished trials; see average_scope).
    average_days: Optional[int] = None
    average_scope: Optional[str] = None
    on_pace: bool


class TrialCompareResponse(Schema):
    signal: str
    # well_below | below | average | above | well_above; None without peers.
    tier: Optional[str] = None
    percentile: Optional[int] = None


class TrialHullResponse(Schema):
    ship_type_id: int
    ship_name: str
    role: str
    count: int
    helpful: bool


class TrialShipsResponse(Schema):
    doctrine_fleets: int
    helpful_fleets: int
    hulls: list[TrialHullResponse]


class TrialFleetResponse(Schema):
    fleet_id: int
    start_time: datetime
    doctrine_name: Optional[str] = None
    ship_type_id: int
    ship_name: str
    # primary | support | utility | secondary (Academy) | off_doctrine;
    # None when the fleet had no doctrine.
    role: Optional[str] = None
    helpful: bool


class TrialKillsResponse(Schema):
    solo: int
    small_gang: int
    fleet: int
    losses: int
    top_ship_type_id: Optional[int] = None
    top_ship_name: Optional[str] = None
    last_kill_at: Optional[datetime] = None


class TrialStatusResponse(Schema):
    on_trial: bool


class TrialReportResponse(Schema):
    on_trial: bool
    corporation_ticker: Optional[str] = None
    trial: Optional[TrialProgressResponse] = None
    compare: Optional[list[TrialCompareResponse]] = None
    academy: bool = False
    ships: Optional[TrialShipsResponse] = None
    fleets: list[TrialFleetResponse] = []


class MemberInsightsResponse(Schema):
    corporation_ticker: Optional[str] = None
    # Live community status, and whether the viewer may promote them.
    on_trial: bool = False
    can_promote: bool = False
    trial: Optional[TrialProgressResponse] = None
    compare: Optional[list[TrialCompareResponse]] = None
    academy: bool = False
    ships: TrialShipsResponse
    kills: TrialKillsResponse
