"""Lightweight dataclasses describing a code-defined survey.

Question sets live in code (not the DB). Every question carries a stable
``key`` so trendable "core" items remain comparable across quarters.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from surveys.constants import (
    NUMERIC_TYPES,
    TYPE_MATRIX,
    TYPE_MULTI,
    TYPE_SINGLE,
)


@dataclass(frozen=True)
class Question:
    key: str  # stable, globally unique (e.g. "core.satisfaction")
    type: str  # one of surveys.constants TYPE_*
    label: str
    help: str = ""
    # For single/multi: the selectable choices. For matrix: the column options.
    choices: Tuple[str, ...] = field(default_factory=tuple)
    # For matrix questions: the (key, label) rows.
    rows: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    required: bool = False
    trendable: bool = False
    # Optional sub-group title within a block; consecutive questions sharing a
    # group render together in one titled sub-card (e.g. "Strategic content").
    group: str = ""
    # Optional endpoint labels for scale endpoints (low, high).
    scale_labels: Optional[Tuple[str, str]] = None
    # For matrix questions whose rows are populated from live platform data
    # rather than hardcoded (e.g. "tribes" → one row per active tribe).
    row_source: str = ""
    # How a matrix's options should be color-coded:
    #   "rating"    → sequential red→green (bad→good), N/A neutral
    #   "diverging" → center-good (green middle, amber ends)
    #   ""          → no gradient; render as a plain select
    scale_kind: str = ""
    # For matrix rows that should be filtered per-member by real usage data
    # (e.g. "service_usage" → only tools the member has interacted with).
    row_filter: str = ""
    # Attaches live display context to a question to fight recency bias
    # (e.g. "content:strategic" → recent fleets + FC portraits for that bracket).
    context_source: str = ""

    def is_numeric(self) -> bool:
        return self.type in NUMERIC_TYPES

    def is_matrix(self) -> bool:
        return self.type == TYPE_MATRIX

    def allows_multiple(self) -> bool:
        return self.type == TYPE_MULTI

    def is_choice(self) -> bool:
        return self.type in (TYPE_SINGLE, TYPE_MULTI)


@dataclass(frozen=True)
class Block:
    key: str
    title: str
    description: str = ""
    questions: Tuple[Question, ...] = field(default_factory=tuple)
    # If set, only members with this community status see the block
    # (e.g. "trial" → onboarding questions only for trial members).
    audience: str = ""


@dataclass(frozen=True)
class SurveyDefinition:
    key: str  # e.g. "community"
    title: str
    blocks: Tuple[Block, ...] = field(default_factory=tuple)

    def all_questions(self) -> List[Question]:
        return [q for b in self.blocks for q in b.questions]

    def question_map(self) -> dict:
        return {q.key: q for q in self.all_questions()}

    def trendable_keys(self) -> List[str]:
        return [q.key for q in self.all_questions() if q.trendable]
