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
    mined_volume: int = 0


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
    """One feed line: "<pilot> <verb> <subject> <tail>". ``action`` is the
    whole line; the parts let the page put an icon before the subject."""

    occurred_at: datetime
    kind: str
    character_id: int
    character_name: str
    others: int
    action: str
    region: str
    verb: str = ""
    subject: str = ""
    # type (a ship or ore), alliance, corporation or faction; empty for none.
    subject_type: str = ""
    subject_id: int = 0
    tail: str = ""
    # Shown on hover over the subject: the ores of a many-ore mining line.
    detail: str = ""
    # m³ for a mining line, ISK destroyed for a fight, LP for a warzone
    # site; 0 otherwise.
    amount: int = 0
    # A mining line names the pilot's main; true when another of their
    # characters did the mining (which one is not public).
    on_alt: bool = False
    # A mining line outside high sec: no pilot (character_id 0, name
    # "Undisclosed Character"), so the page shows no portrait.
    undisclosed: bool = False


class LandingPulseResponse(Schema):
    generated_at: datetime
    delay_minutes: int
    day: LandingDayTotals
    hourly_kills: List[LandingHourlyKills]
    week: LandingWeekTotals
    timezone_kills: List[LandingTimezoneKills]
    moments: List[LandingMoment]
    events: List[LandingEvent]


class LandingWeekCounts(Schema):
    fights: int
    kills: int
    warzone: int
    mining: int
    industry: int


class LandingWeekResponse(Schema):
    generated_at: datetime
    tab: str
    page: int
    pages: int
    per_page: int
    total: int
    counts: LandingWeekCounts
    rows: List[LandingEvent]
