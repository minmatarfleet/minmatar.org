from typing import Any, Dict, List, Optional

from ninja import Schema


# ---- Question / definition rendering ----
class QuestionSchema(Schema):
    key: str
    type: str
    label: str
    help: str = ""
    choices: List[str] = []
    rows: List[Dict[str, Any]] = (
        []
    )  # [{"key","label","hint","chief_id","chief_name"}]
    required: bool = False
    trendable: bool = False
    group: str = ""
    scale_labels: Optional[List[str]] = None
    scale_kind: str = ""
    context: Optional[Dict[str, Any]] = (
        None  # live display context (fights recency bias)
    )


class BlockSchema(Schema):
    key: str
    title: str
    description: str = ""
    questions: List[QuestionSchema] = []


class SurveyQuestionsSchema(Schema):
    campaign_id: int
    definition_key: str
    title: str
    member_blocks: List[BlockSchema] = []


# ---- Member context (autofill) ----
class TribeRefSchema(Schema):
    key: str = ""
    label: str = ""
    chief_id: Optional[int] = None
    chief_name: str = ""
    hint: str = ""


class MemberContextSchema(Schema):
    character_id: Optional[int] = None
    character_name: str = ""
    corporation_id: Optional[int] = None
    corporation_name: str = ""
    ceo_id: Optional[int] = None
    ceo_name: str = ""
    corp_history: List[Dict[str, Any]] = []
    graduated: bool = False
    prime_time: str = ""
    tribes: List[TribeRefSchema] = []
    tribe_names: List[str] = []
    community_status: str = ""
    tenure_days: Optional[int] = None
    tenure_cohort: str = ""
    joined_at: Optional[str] = None
    fleets_attended_quarter: int = 0
    activity_tier: str = ""
    role_flags: List[str] = []
    guides_completed: int = 0
    persona: str = ""
    tenure_note: str = ""
    fleets_note: str = ""
    guides_note: str = ""
    timezone_note: str = ""


# ---- Campaign ----
class CampaignSchema(Schema):
    id: int
    year: int
    quarter: int
    definition_key: str
    title: str
    status: str
    opens_at: Optional[str] = None
    closes_at: Optional[str] = None
    response_count: int = 0


class ActiveSurveySchema(Schema):
    campaign: Optional[CampaignSchema] = None
    has_responded: bool = False


class MyResponseSchema(Schema):
    answers: Dict[str, Any] = {}
    has_responded: bool = False
    submitted_at: Optional[str] = None


# ---- Submission ----
class AnswerInput(Schema):
    question_key: str
    value: Any = None  # number | string | list | dict(matrix)


class SubmitResponseRequest(Schema):
    answers: List[AnswerInput] = []
    context_corrections: Dict[str, Any] = {}


class SubmitResult(Schema):
    ok: bool
    response_id: Optional[int] = None
    detail: str = ""


# ---- Give-back ----
class GivebackPersonalSchema(Schema):
    fleets_flown: int = 0
    doctrines_ready: int = 0
    guides_completed: int = 0
    srp_count: int = 0
    srp_isk: float = 0
    tribe: str = "—"


class GivebackCommunitySchema(Schema):
    active_pilots: Optional[int] = None


class GivebackSchema(Schema):
    personal: GivebackPersonalSchema
    community: GivebackCommunitySchema


# ---- Changelog ----
class ChangelogEntrySchema(Schema):
    heading: str
    body_markdown: str = ""
    sort_order: int = 0


class ChangelogEntryInput(Schema):
    heading: str
    body_markdown: str = ""
    sort_order: int = 0
    published: bool = True


# ---- Results / trends ----
class AggregateSchema(Schema):
    question_key: str
    segment_key: str
    n: int
    mean: Optional[float] = None
    distribution: Dict[str, float] = {}


class ResultsSchema(Schema):
    campaign_id: int
    segment_key: str
    aggregates: List[AggregateSchema] = []


# ---- Campaign create/update ----
class CreateCampaignRequest(Schema):
    year: int
    quarter: int
    definition_key: Optional[str] = (
        None  # falls back to the quarter's template
    )
    title: Optional[str] = None
    open_now: bool = False


class UpdateCampaignRequest(Schema):
    status: Optional[str] = None
    opens_at: Optional[str] = None
    closes_at: Optional[str] = None
