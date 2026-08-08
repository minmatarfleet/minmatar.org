"""Alliance health API schemas and payload helpers."""

from typing import Any, Literal, Union

from pydantic import BaseModel


class StatusCounts(BaseModel):
    active: int
    trial: int
    on_leave: int


class Signals30(BaseModel):
    fleets: int
    small_gang: int
    solo: int
    supply: int


class QuietCounts(BaseModel):
    fading: int
    dark: int
    seasonal: int


class MonthlyPoint(BaseModel):
    month: str
    label: str
    active: int
    fleet: int
    solo: int
    supply: int


class HealthOverviewResponse(BaseModel):
    computed_at: str
    goal_map: int
    map_7d: int
    map_14d: int
    map_30d: int
    roster_people: int
    status: StatusCounts
    signals_30d: Signals30
    quiet: QuietCounts
    monthly: list[MonthlyPoint]


class AttentionPilot(BaseModel):
    user_id: int
    pilot: str
    corp: str
    status: str
    days_quiet: Union[int, str]
    active_months: int
    character_id: int | None = None
    corporation_id: int | None = None


class HealthAttentionResponse(BaseModel):
    computed_at: str
    bucket: Literal["fading", "dark", "seasonal"]
    pilots: list[AttentionPilot]


class CorporationHealthRow(BaseModel):
    corporation_id: int
    name: str
    characters: int
    humans: int
    active_90d: int
    active_90d_pct: float
    growth_90d_pct: float


class HealthCorporationsResponse(BaseModel):
    computed_at: str
    corporations: list[CorporationHealthRow]


class CohortRow(BaseModel):
    month: str
    label: str
    applications: int
    accepts: int
    academy_accepts: int
    fleet_first_week_pct: float
    fleet_1_30d_pct: float
    fleet_3_30d_pct: float


class HealthCohortsResponse(BaseModel):
    computed_at: str
    cohorts: list[CohortRow]


AttentionBucket = Literal["fading", "dark", "seasonal"]


def overview_from_payload(payload: dict[str, Any]) -> HealthOverviewResponse:
    return HealthOverviewResponse(
        computed_at=payload["computed_at"],
        goal_map=payload["goal_map"],
        map_7d=payload["map_7d"],
        map_14d=payload["map_14d"],
        map_30d=payload["map_30d"],
        roster_people=payload["roster_people"],
        status=StatusCounts(**payload["status"]),
        signals_30d=Signals30(**payload["signals_30d"]),
        quiet=QuietCounts(**payload["quiet"]),
        monthly=[MonthlyPoint(**m) for m in payload.get("monthly", [])],
    )


def attention_from_payload(
    payload: dict[str, Any], bucket: AttentionBucket
) -> HealthAttentionResponse:
    pilots = payload.get("attention", {}).get(bucket, [])
    return HealthAttentionResponse(
        computed_at=payload["computed_at"],
        bucket=bucket,
        pilots=[AttentionPilot(**p) for p in pilots],
    )


def corporations_from_payload(
    payload: dict[str, Any],
) -> HealthCorporationsResponse:
    return HealthCorporationsResponse(
        computed_at=payload["computed_at"],
        corporations=[
            CorporationHealthRow(**c) for c in payload.get("corporations", [])
        ],
    )


def cohorts_from_payload(payload: dict[str, Any]) -> HealthCohortsResponse:
    return HealthCohortsResponse(
        computed_at=payload["computed_at"],
        cohorts=[CohortRow(**c) for c in payload.get("cohorts", [])],
    )
