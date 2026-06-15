"""Report types for tribe catalog bindings."""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Callable


class ReportScope(str, Enum):
    ROSTER = "roster"
    ALLIANCE = "alliance"
    PROGRAM = "program"


class ReportView(str, Enum):
    TOWN_HALL = "town_hall"
    MEMBER = "member"


@dataclass(frozen=True)
class PeriodBounds:
    label: str
    start: date
    end: date  # inclusive calendar date for mining; datetime end for fleets


@dataclass(frozen=True)
class QuerySpec:
    query_key: str
    scope: ReportScope
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ReportBinding:
    code: str
    manual: bool = False
    manual_message: str = ""
    views: dict[str, QuerySpec] = field(default_factory=dict)
    presentation: dict = field(default_factory=dict)


@dataclass
class ReportResult:
    group_id: int
    group_code: str
    group_name: str
    view: str
    scope: str
    period: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    manual: bool = False
    message: str = ""
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    totals: dict[str, Any] = field(default_factory=dict)


QueryRunner = Callable[
    ["TribeGroup", PeriodBounds, ReportScope, dict],
    tuple[list[dict[str, Any]], dict[str, Any], list[str]],
]

# TribeGroup forward ref — imported at runtime in runner
TribeGroup = Any  # pylint: disable=invalid-name
