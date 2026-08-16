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


class TrialHygieneCounts(BaseModel):
    approve: int = 0
    too_early: int = 0
    fail: int = 0
    nudge: int = 0
    hold: int = 0


class LeaveHygieneCounts(BaseModel):
    recommended: int = 0
    kept: int = 0
    exempt: int = 0


class HygieneCounts(BaseModel):
    trial: TrialHygieneCounts
    leave: LeaveHygieneCounts


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
    hygiene: HygieneCounts


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


class TrialHygienePilot(BaseModel):
    user_id: int
    username: str
    pilot: str
    corp: str
    corporation_id: int | None = None
    character_id: int | None = None
    alliance_days: int | None = None
    fleets: int
    kills: int
    kills_small: int
    voice_hours: float
    slice_30d: str
    days_since_activity: int | None = None
    path: str
    conf: str
    reason: str


class HealthTrialsResponse(BaseModel):
    computed_at: str
    bucket: Literal["approve", "too_early", "fail", "nudge"]
    counts: TrialHygieneCounts
    pilots: list[TrialHygienePilot]


class LeaveHygienePilot(BaseModel):
    user_id: int
    username: str
    pilot: str
    corp: str
    corporation_id: int | None = None
    character_id: int | None = None
    fleets: int
    kills: int
    voice_hours: float
    story: str
    conf: str
    reason: str


class HealthLeaveResponse(BaseModel):
    computed_at: str
    counts: LeaveHygieneCounts
    pilots: list[LeaveHygienePilot]


AttentionBucket = Literal["fading", "dark", "seasonal"]
TrialBucket = Literal["approve", "too_early", "fail", "nudge"]


def hygiene_counts_from_payload(payload: dict[str, Any]) -> HygieneCounts:
    hygiene = payload.get("hygiene") or {}
    trial = hygiene.get("trial", {}).get("counts") or {}
    leave = hygiene.get("leave", {}).get("counts") or {}
    return HygieneCounts(
        trial=TrialHygieneCounts(**trial),
        leave=LeaveHygieneCounts(**leave),
    )


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
        hygiene=hygiene_counts_from_payload(payload),
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


def trials_from_payload(
    payload: dict[str, Any], bucket: TrialBucket
) -> HealthTrialsResponse:
    hygiene = payload.get("hygiene") or {}
    trial = hygiene.get("trial") or {}
    counts = TrialHygieneCounts(**(trial.get("counts") or {}))
    pilots = trial.get("buckets", {}).get(bucket, [])
    return HealthTrialsResponse(
        computed_at=payload["computed_at"],
        bucket=bucket,
        counts=counts,
        pilots=[TrialHygienePilot(**p) for p in pilots],
    )


def leave_from_payload(payload: dict[str, Any]) -> HealthLeaveResponse:
    hygiene = payload.get("hygiene") or {}
    leave = hygiene.get("leave") or {}
    counts = LeaveHygieneCounts(**(leave.get("counts") or {}))
    pilots = leave.get("recommended") or []
    return HealthLeaveResponse(
        computed_at=payload["computed_at"],
        counts=counts,
        pilots=[LeaveHygienePilot(**p) for p in pilots],
    )


def trial_csv_lines(pilots: list[TrialHygienePilot]) -> str:
    lines = ["username,community_status,reason"]
    for p in pilots:
        reason = p.reason.replace('"', "'")[:255]
        lines.append(f'{p.username},active,"{reason}"')
    return "\n".join(lines) + "\n"


def leave_csv_lines(pilots: list[LeaveHygienePilot]) -> str:
    lines = ["username,community_status,reason"]
    for p in pilots:
        reason = p.reason.replace('"', "'")[:255]
        lines.append(f'{p.username},on_leave,"{reason}"')
    return "\n".join(lines) + "\n"
