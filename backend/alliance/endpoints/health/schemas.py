"""Alliance health API schemas and payload helpers."""

from typing import Any, Literal, Protocol, TypeVar, Union

from pydantic import BaseModel

from alliance.helpers.health import is_gone_for_months_pilot
from alliance.helpers.hygiene import (
    classify_onboarding_need,
    trial_under_min_tenure,
)
from alliance.helpers.player_prime_time import prime_time_labels_for_users

CountModelT = TypeVar("CountModelT", bound=BaseModel)


class StatusCounts(BaseModel):
    active: int = 0
    trial: int = 0
    on_leave: int = 0


class StatusWindowCounts(BaseModel):
    d30: int = 0
    d90: int = 0
    d180: int = 0


class StatusWindows(BaseModel):
    active: StatusWindowCounts = StatusWindowCounts()
    trial: StatusWindowCounts = StatusWindowCounts()
    on_leave: StatusWindowCounts = StatusWindowCounts()


class Signals30(BaseModel):
    fleets: int = 0
    small_gang: int = 0
    solo: int = 0
    supply: int = 0


class QuietCounts(BaseModel):
    fading: int = 0
    dark: int = 0
    seasonal: int = 0


class MonthlyPoint(BaseModel):
    month: str
    label: str
    active: int
    fleet: int
    small_gang: int = 0
    solo: int
    supply: int = 0


class TrialHygieneCounts(BaseModel):
    approve: int = 0
    too_early: int = 0
    fail: int = 0
    nudge: int = 0
    hold: int = 0
    current: int = 0
    add: int = 0
    remove: int = 0
    flagged: int = 0
    passing: int = 0
    failing: int = 0
    evaluating: int = 0


class LeaveHygieneCounts(BaseModel):
    recommended: int = 0
    kept: int = 0
    exempt: int = 0
    current: int = 0
    add: int = 0
    remove: int = 0
    flagged: int = 0
    inactive: int = 0
    returning: int = 0


class HygieneCounts(BaseModel):
    trial: TrialHygieneCounts
    leave: LeaveHygieneCounts


class TribeMonthlySeries(BaseModel):
    tribe_id: int
    name: str
    counts: list[int]


class TribeMonthLabel(BaseModel):
    month: str
    label: str


class TribesMonthlyResponse(BaseModel):
    months: list[TribeMonthLabel] = []
    series: list[TribeMonthlySeries] = []


class UnknownCharacter(BaseModel):
    character_id: int
    character_name: str
    corporation_id: int
    corp: str


class ViewerContext(BaseModel):
    alliance_wide: bool = True
    home_corp_id: int | None = None
    can_mutate: bool = False
    can_leave_any: bool = False
    officer_corp_ids: list[int] = []
    ceo_corp_ids: list[int] = []


class StatusDelta30(BaseModel):
    active: int = 0
    trial: int = 0
    on_leave: int = 0


class HealthOverviewResponse(BaseModel):
    computed_at: str
    goal_map: int
    map_7d: int
    map_14d: int
    map_30d: int
    roster_people: int
    status: StatusCounts
    status_windows: StatusWindows
    signals_30d: Signals30
    quiet: QuietCounts
    monthly: list[MonthlyPoint]
    tribes_monthly: TribesMonthlyResponse
    unknown_characters: list[UnknownCharacter] = []
    hygiene: HygieneCounts
    viewer: ViewerContext
    delta_30d: StatusDelta30 = StatusDelta30()


class AttentionPilot(BaseModel):
    user_id: int
    pilot: str
    corp: str
    status: str
    days_quiet: Union[int, str]
    active_months: int
    character_id: int | None = None
    corporation_id: int | None = None
    timezone: str | None = None


class HealthAttentionResponse(BaseModel):
    computed_at: str
    bucket: Literal["fading", "dark", "seasonal"]
    pilots: list[AttentionPilot]
    counts: QuietCounts = QuietCounts()
    counts_by_corp: dict[str, QuietCounts] = {}


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


class OnboardingCounts(BaseModel):
    first_week: int = 0
    more_fleets: int = 0


AttentionBucket = Literal["fading", "dark", "seasonal"]
TrialBucket = Literal[
    "current",
    "passing",
    "failing",
    "evaluating",
    "add",
    "remove",
    "flagged",
    "approve",
    "too_early",
    "fail",
    "nudge",
]
LeaveBucket = Literal[
    "current",
    "inactive",
    "returning",
    "add",
    "remove",
    "flagged",
]


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
    decision: str | None = None
    timezone: str | None = None


class HealthTrialsResponse(BaseModel):
    computed_at: str
    bucket: TrialBucket
    counts: TrialHygieneCounts
    counts_by_corp: dict[str, TrialHygieneCounts] = {}
    pilots: list[TrialHygienePilot]


class HealthOnboardingResponse(BaseModel):
    computed_at: str
    bucket: Literal["first_week", "more_fleets"]
    counts: OnboardingCounts
    counts_by_corp: dict[str, OnboardingCounts] = {}
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
    timezone: str | None = None


class HealthLeaveResponse(BaseModel):
    computed_at: str
    bucket: LeaveBucket
    counts: LeaveHygieneCounts
    counts_by_corp: dict[str, LeaveHygieneCounts] = {}
    pilots: list[LeaveHygienePilot]


class HealthUnknownsResponse(BaseModel):
    computed_at: str
    characters: list[UnknownCharacter]


class HealthStatusChangeRequest(BaseModel):
    user_id: int
    action: Literal["promote", "leave", "restore"]
    reason: str = ""


class HealthStatusChangeResponse(BaseModel):
    user_id: int
    status: str
    detail: str


class _HasUserTimezone(Protocol):
    user_id: int
    timezone: str | None


PilotT = TypeVar("PilotT", bound=_HasUserTimezone)


def _apply_timezones(pilots: list[PilotT]) -> list[PilotT]:
    labels = prime_time_labels_for_users(p.user_id for p in pilots)
    for pilot in pilots:
        pilot.timezone = labels.get(pilot.user_id)
    return pilots


def status_windows_from_payload(payload: dict[str, Any]) -> StatusWindows:
    raw = payload.get("status_windows") or {}
    return StatusWindows(
        active=StatusWindowCounts(**(raw.get("active") or {})),
        trial=StatusWindowCounts(**(raw.get("trial") or {})),
        on_leave=StatusWindowCounts(**(raw.get("on_leave") or {})),
    )


def tribes_monthly_from_payload(
    payload: dict[str, Any],
) -> TribesMonthlyResponse:
    raw = payload.get("tribes_monthly") or {}
    months = [TribeMonthLabel(**m) for m in raw.get("months") or []]
    series = [TribeMonthlySeries(**s) for s in raw.get("series") or []]
    return TribesMonthlyResponse(months=months, series=series)


def unknown_characters_from_payload(
    payload: dict[str, Any],
) -> list[UnknownCharacter]:
    return [
        UnknownCharacter(**row)
        for row in payload.get("unknown_characters") or []
    ]


def hygiene_counts_from_payload(  # noqa: C901
    payload: dict[str, Any],
) -> HygieneCounts:
    hygiene = payload.get("hygiene") or {}
    trial = (hygiene.get("trial") or {}).get("counts") or {}
    leave = (hygiene.get("leave") or {}).get("counts") or {}
    buckets = (hygiene.get("trial") or {}).get("buckets") or {}
    counts = HygieneCounts(
        trial=TrialHygieneCounts(**trial),
        leave=LeaveHygieneCounts(**leave),
    )
    if counts.trial.remove == 0 and counts.trial.approve:
        counts.trial.remove = counts.trial.approve
    if counts.trial.flagged == 0:
        counts.trial.flagged = counts.trial.fail + counts.trial.nudge
    if counts.trial.passing == 0:
        if buckets.get("passing"):
            counts.trial.passing = sum(
                1
                for row in buckets["passing"]
                if not trial_under_min_tenure(row.get("alliance_days"))
            )
        else:
            counts.trial.passing = counts.trial.approve
    if counts.trial.failing == 0:
        if buckets.get("failing"):
            counts.trial.failing = sum(
                1
                for row in buckets["failing"]
                if not trial_under_min_tenure(row.get("alliance_days"))
            )
        else:
            counts.trial.failing = counts.trial.fail
    if counts.trial.evaluating == 0:
        if buckets.get("evaluating"):
            counts.trial.evaluating = len(buckets["evaluating"])
        else:
            counts.trial.evaluating = (
                counts.trial.nudge + counts.trial.hold + counts.trial.too_early
            )
    if counts.trial.current == 0:
        if buckets.get("current"):
            counts.trial.current = len(buckets["current"])
        else:
            counts.trial.current = sum(
                len(buckets.get(key) or [])
                for key in ("approve", "too_early", "fail", "nudge", "hold")
            )
    if counts.leave.add == 0:
        counts.leave.add = counts.leave.recommended
    if counts.leave.returning == 0:
        counts.leave.returning = counts.leave.remove
    if counts.leave.inactive == 0:
        counts.leave.inactive = max(
            0, counts.leave.current - counts.leave.returning
        )
    return counts


def _status_headcount(payload: dict[str, Any], key: str) -> int:
    status = payload.get("status") or {}
    if key in status:
        return int(status.get(key) or 0)
    windows = (payload.get("status_windows") or {}).get(key) or {}
    return int(windows.get("d30") or 0)


def status_delta_30d(
    current: dict[str, Any], prior: dict[str, Any] | None
) -> StatusDelta30:
    if not prior:
        return StatusDelta30()
    return StatusDelta30(
        active=_status_headcount(current, "active")
        - _status_headcount(prior, "active"),
        trial=_status_headcount(current, "trial")
        - _status_headcount(prior, "trial"),
        on_leave=_status_headcount(current, "on_leave")
        - _status_headcount(prior, "on_leave"),
    )


def overview_from_payload(
    payload: dict[str, Any],
    viewer: ViewerContext | None = None,
    prior_payload: dict[str, Any] | None = None,
) -> HealthOverviewResponse:
    return HealthOverviewResponse(
        computed_at=str(payload.get("computed_at") or ""),
        goal_map=int(payload.get("goal_map") or 0),
        map_7d=int(payload.get("map_7d") or 0),
        map_14d=int(payload.get("map_14d") or 0),
        map_30d=int(payload.get("map_30d") or 0),
        roster_people=int(payload.get("roster_people") or 0),
        status=StatusCounts(**(payload.get("status") or {})),
        status_windows=status_windows_from_payload(payload),
        signals_30d=Signals30(**(payload.get("signals_30d") or {})),
        quiet=quiet_counts_from_payload(payload),
        monthly=[MonthlyPoint(**m) for m in payload.get("monthly") or []],
        tribes_monthly=tribes_monthly_from_payload(payload),
        unknown_characters=unknown_characters_from_payload(payload),
        hygiene=hygiene_counts_from_payload(payload),
        viewer=viewer or ViewerContext(),
        delta_30d=status_delta_30d(payload, prior_payload),
    )


def _row_corp_name(row: Any) -> str:
    if isinstance(row, dict):
        name = row.get("corp") or ""
    else:
        name = getattr(row, "corp", None) or ""
    return str(name).strip() or "—"


def counts_by_corp_from_bucket_rows(
    bucket_rows: dict[str, list],
    model_cls: type[CountModelT],
) -> dict[str, CountModelT]:
    fields = tuple(model_cls.model_fields)
    empty = {field: 0 for field in fields}
    tallies: dict[str, dict[str, int]] = {"all": dict(empty)}
    for bucket, rows in bucket_rows.items():
        if bucket not in model_cls.model_fields:
            continue
        tallies["all"][bucket] = len(rows)
        for row in rows:
            corp = _row_corp_name(row)
            slot = tallies.setdefault(corp, dict(empty))
            slot[bucket] = slot.get(bucket, 0) + 1
    return {name: model_cls(**vals) for name, vals in tallies.items()}


def quiet_counts_from_payload(payload: dict[str, Any]) -> QuietCounts:
    quiet = QuietCounts(**(payload.get("quiet") or {}))
    dark_rows = (payload.get("attention") or {}).get("dark")
    if dark_rows is not None:
        quiet.dark = sum(
            1
            for row in dark_rows
            if is_gone_for_months_pilot(
                row.get("days_quiet"), row.get("active_months")
            )
        )
    return quiet


def _attention_bucket_rows(
    payload: dict[str, Any], bucket: AttentionBucket
) -> list:
    pilots = list(payload.get("attention", {}).get(bucket, []) or [])
    if bucket == "dark":
        pilots = [
            row
            for row in pilots
            if is_gone_for_months_pilot(
                row.get("days_quiet"), row.get("active_months")
            )
        ]
    return pilots


def attention_from_payload(
    payload: dict[str, Any], bucket: AttentionBucket
) -> HealthAttentionResponse:
    bucket_rows = {
        name: _attention_bucket_rows(payload, name)
        for name in ("fading", "dark", "seasonal")
    }
    by_corp = counts_by_corp_from_bucket_rows(bucket_rows, QuietCounts)
    return HealthAttentionResponse(
        computed_at=str(payload.get("computed_at") or ""),
        bucket=bucket,
        counts=by_corp.get("all", QuietCounts()),
        counts_by_corp=by_corp,
        pilots=_apply_timezones(
            [AttentionPilot(**p) for p in bucket_rows[bucket]]
        ),
    )


def corporations_from_payload(
    payload: dict[str, Any],
) -> HealthCorporationsResponse:
    return HealthCorporationsResponse(
        computed_at=str(payload.get("computed_at") or ""),
        corporations=[
            CorporationHealthRow(**c)
            for c in payload.get("corporations") or []
        ],
    )


def cohorts_from_payload(payload: dict[str, Any]) -> HealthCohortsResponse:
    return HealthCohortsResponse(
        computed_at=str(payload.get("computed_at") or ""),
        cohorts=[CohortRow(**c) for c in payload.get("cohorts") or []],
    )


def _trial_row_user_id(row: Any) -> Any:
    if isinstance(row, dict):
        return row.get("user_id")
    return getattr(row, "user_id", None)


def _trial_row_alliance_days(row: Any) -> int | None:
    if isinstance(row, dict):
        return row.get("alliance_days")
    return getattr(row, "alliance_days", None)


def _trial_extend_unique(target: list, rows: list, seen: set) -> None:
    for row in rows:
        uid = _trial_row_user_id(row)
        if uid in seen:
            continue
        seen.add(uid)
        target.append(row)


def _trial_bucket_rows(trial: dict[str, Any], bucket: TrialBucket) -> list:
    buckets = trial.get("buckets") or {}
    if bucket == "remove":
        return buckets.get("remove") or buckets.get("approve") or []
    if bucket == "flagged":
        return buckets.get("flagged") or (
            (buckets.get("fail") or []) + (buckets.get("nudge") or [])
        )
    if bucket == "add":
        return buckets.get("add") or []
    if bucket == "current":
        pilots = buckets.get("current") or []
        if not pilots:
            for key in ("approve", "too_early", "fail", "nudge", "hold"):
                pilots = pilots + (buckets.get(key) or [])
        return pilots
    if bucket in ("passing", "failing", "evaluating"):
        return _trial_selector_rows(trial)[bucket]
    return buckets.get(bucket) or []


def _trial_selector_rows(trial: dict[str, Any]) -> dict[str, list]:
    buckets = trial.get("buckets") or {}

    def raw(name: str, fallbacks: tuple[str, ...]) -> list:
        if buckets.get(name):
            return list(buckets[name])
        rows: list = []
        for key in fallbacks:
            rows.extend(buckets.get(key) or [])
        return rows

    passing_raw = raw("passing", ("approve", "too_early"))
    failing_raw = raw("failing", ("fail",))
    evaluating = raw("evaluating", ("nudge", "hold"))
    passing: list = []
    failing: list = []
    early: list = []
    for row in passing_raw:
        if trial_under_min_tenure(_trial_row_alliance_days(row)):
            early.append(row)
        else:
            passing.append(row)
    for row in failing_raw:
        if trial_under_min_tenure(_trial_row_alliance_days(row)):
            early.append(row)
        else:
            failing.append(row)
    seen = {_trial_row_user_id(row) for row in evaluating}
    _trial_extend_unique(evaluating, buckets.get("too_early") or [], seen)
    _trial_extend_unique(evaluating, early, seen)
    return {
        "passing": passing,
        "failing": failing,
        "evaluating": evaluating,
    }


def trials_from_payload(
    payload: dict[str, Any], bucket: TrialBucket
) -> HealthTrialsResponse:
    hygiene = payload.get("hygiene") or {}
    trial = hygiene.get("trial") or {}
    counts = TrialHygieneCounts(**(trial.get("counts") or {}))
    tab_rows = {
        name: _trial_bucket_rows(trial, name)
        for name in ("current", "passing", "failing", "evaluating")
    }
    by_corp = counts_by_corp_from_bucket_rows(tab_rows, TrialHygieneCounts)
    all_counts = by_corp.get("all", TrialHygieneCounts())
    counts.current = all_counts.current
    counts.passing = all_counts.passing
    counts.failing = all_counts.failing
    counts.evaluating = all_counts.evaluating
    return HealthTrialsResponse(
        computed_at=str(payload.get("computed_at") or ""),
        bucket=bucket,
        counts=counts,
        counts_by_corp=by_corp,
        pilots=_apply_timezones(
            [TrialHygienePilot(**p) for p in _trial_bucket_rows(trial, bucket)]
        ),
    )


def onboarding_from_payload(
    payload: dict[str, Any],
    bucket: Literal["first_week", "more_fleets"] = "first_week",
) -> HealthOnboardingResponse:
    current = trials_from_payload(payload, "current")
    first_week: list[TrialHygienePilot] = []
    more_fleets: list[TrialHygienePilot] = []
    for pilot in current.pilots:
        need = classify_onboarding_need(
            fleets=pilot.fleets,
            alliance_days=pilot.alliance_days,
        )
        if need == "first_week":
            first_week.append(pilot)
        elif need == "more_fleets":
            more_fleets.append(pilot)
    by_corp = counts_by_corp_from_bucket_rows(
        {"first_week": first_week, "more_fleets": more_fleets},
        OnboardingCounts,
    )
    return HealthOnboardingResponse(
        computed_at=str(payload.get("computed_at") or ""),
        bucket=bucket,
        counts=by_corp.get(
            "all",
            OnboardingCounts(
                first_week=len(first_week),
                more_fleets=len(more_fleets),
            ),
        ),
        counts_by_corp=by_corp,
        pilots=first_week if bucket == "first_week" else more_fleets,
    )


def _fill_leave_selector_counts(
    counts: LeaveHygieneCounts, leave: dict[str, Any]
) -> LeaveHygieneCounts:
    if counts.add == 0:
        counts.add = counts.recommended
    if counts.returning == 0:
        if leave.get("returning"):
            counts.returning = len(leave["returning"])
        else:
            counts.returning = counts.remove or len(
                leave.get("restore") or leave.get("remove") or []
            )
    if counts.inactive == 0:
        if leave.get("inactive"):
            counts.inactive = len(leave["inactive"])
        else:
            current_n = counts.current or len(leave.get("current") or [])
            counts.inactive = max(0, current_n - counts.returning)
    return counts


def _leave_bucket_rows(leave: dict[str, Any], bucket: LeaveBucket) -> list:
    if bucket == "add":
        return leave.get("recommended") or leave.get("add") or []
    if bucket in ("remove", "returning"):
        return (
            leave.get("returning")
            or leave.get("restore")
            or leave.get("remove")
            or []
        )
    if bucket == "inactive":
        pilots = leave.get("inactive") or []
        if not pilots:
            current = leave.get("current") or []
            returning = (
                leave.get("returning")
                or leave.get("restore")
                or leave.get("remove")
                or []
            )
            returning_ids = {row.get("user_id") for row in returning}
            pilots = [
                row
                for row in current
                if row.get("user_id") not in returning_ids
            ]
        return pilots
    return leave.get(bucket) or []


def leave_from_payload(
    payload: dict[str, Any], bucket: LeaveBucket = "current"
) -> HealthLeaveResponse:
    hygiene = payload.get("hygiene") or {}
    leave = hygiene.get("leave") or {}
    counts = _fill_leave_selector_counts(
        LeaveHygieneCounts(**(leave.get("counts") or {})), leave
    )
    tab_rows = {
        name: _leave_bucket_rows(leave, name)
        for name in ("current", "inactive", "returning")
    }
    by_corp = counts_by_corp_from_bucket_rows(tab_rows, LeaveHygieneCounts)
    all_counts = by_corp.get("all", LeaveHygieneCounts())
    counts.current = all_counts.current
    counts.inactive = all_counts.inactive
    counts.returning = all_counts.returning
    return HealthLeaveResponse(
        computed_at=str(payload.get("computed_at") or ""),
        bucket=bucket,
        counts=counts,
        counts_by_corp=by_corp,
        pilots=_apply_timezones(
            [LeaveHygienePilot(**p) for p in _leave_bucket_rows(leave, bucket)]
        ),
    )


def trial_csv_lines(pilots: list[TrialHygienePilot]) -> str:
    lines = ["username,community_status,reason"]
    for p in pilots:
        reason = p.reason.replace('"', "'")[:255]
        lines.append(f'{p.username},active,"{reason}"')
    return "\n".join(lines) + "\n"


def leave_csv_lines(
    pilots: list[LeaveHygienePilot], bucket: LeaveBucket = "add"
) -> str:
    status = "active" if bucket in ("remove", "returning") else "on_leave"
    lines = ["username,community_status,reason"]
    for p in pilots:
        reason = p.reason.replace('"', "'")[:255]
        lines.append(f'{p.username},{status},"{reason}"')
    return "\n".join(lines) + "\n"
