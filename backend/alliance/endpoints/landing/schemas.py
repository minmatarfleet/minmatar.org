from datetime import datetime
from typing import List, Optional

from ninja import Schema


class LandingDayTotals(Schema):
    ships_destroyed: int
    ships_lost: int
    warzone_sites: int
    complexes: int
    industry_jobs: int
    freight_contracts: int
    freight_volume: int


class LandingWeekTotals(Schema):
    ships_destroyed: int
    warzone_sites: int
    complexes: int
    fleets: int
    peak_comms: int
    peak_comms_at: Optional[datetime] = None
    freight_contracts: int
    freight_volume: int
    industry_jobs: int


class LandingHourlyKills(Schema):
    hour: int
    kills: int


class LandingTimezoneKills(Schema):
    hour: int
    average_kills: float


class LandingMoment(Schema):
    kind: str
    occurred_at: datetime
    title: str
    value: float
    unit: str


class LandingEvent(Schema):
    occurred_at: datetime
    kind: str
    character_id: int
    character_name: str
    others: int
    action: str
    region: str


class LandingPulseResponse(Schema):
    generated_at: datetime
    delay_minutes: int
    day: LandingDayTotals
    hourly_kills: List[LandingHourlyKills]
    week: LandingWeekTotals
    timezone_kills: List[LandingTimezoneKills]
    moments: List[LandingMoment]
    events: List[LandingEvent]
