"""Request and response schemas for /api/learning/mentors."""

from datetime import datetime

from ninja import Schema


class AvailabilitySchema(Schema):
    weekday_brackets: list[str]
    weekend_brackets: list[str]
    days: list[int]


class MentorPersonSchema(Schema):
    user_id: int
    name: str
    character_id: int | None
    portrait: str
    corp: str
    corporation_id: int | None
    discord_handle: str
    discord_id: str | None


class MentorClassRefSchema(Schema):
    id: int
    slug: str
    title: str
    minutes: int
    where: str
    status: str
    cover_image_url: str = ""


class MentorCardSchema(Schema):
    mentor_id: int
    person: MentorPersonSchema
    availability: AvailabilitySchema
    fit: str
    answer_hours: float | None
    answer_text: str
    queue: int
    classes_taught: int
    pilots_mentored: int = 0
    full: bool
    classes: list[MentorClassRefSchema]
    is_you: bool = False


class MentorRequestSchema(Schema):
    id: int
    status: str
    mentor_class: MentorClassRefSchema
    pilot: MentorPersonSchema
    mentor: MentorPersonSchema
    mentor_id: int
    note: str
    starts_at: datetime | None
    bring: str
    created_at: datetime
    answered_at: datetime | None
    availability: AvailabilitySchema
    passed_from_name: str
    answer_text: str
    pilot_rating: str
    mentor_outcome: str
    can_give_feedback: bool


class MentorsHomeResponse(Schema):
    can_request: bool
    is_mentor: bool
    mentor_status: str | None
    can_manage: bool
    open_asks: int
    availability: AvailabilitySchema
    classes: list[MentorRequestSchema]
    past_count: int
    mentors: list[MentorCardSchema]


class MentorsMeResponse(Schema):
    can_request: bool
    is_mentor: bool
    mentor_status: str | None
    can_manage: bool
    open_asks: int


class RequirementCheckSchema(Schema):
    kind: str
    value: str
    label: str
    met: bool
    detail: str


class MentorClassDetailResponse(Schema):
    id: int
    slug: str
    title: str
    summary: str
    outline: list[str]
    minutes: int
    where: str
    cover_image_url: str
    status: str
    author: MentorPersonSchema | None
    requirements: list[RequirementCheckSchema]
    all_met: bool
    mentors: list[MentorCardSchema]
    pilots_taught: int
    can_edit: bool
    open_request_id: int | None


class CreateMentorRequestBody(Schema):
    mentor_id: int
    class_id: int
    note: str = ""
    weekday_brackets: list[str] = []
    weekend_brackets: list[str] = []
    days: list[int] = []


class MentorRecordSchema(Schema):
    classes_taught: int
    pilots_mentored: int
    still_flying: int


class MentoringResponse(Schema):
    record: MentorRecordSchema
    asks: list[MentorRequestSchema]
    booked: list[MentorRequestSchema]
    to_close: list[MentorRequestSchema]
    past_count: int


class MentorSlotsResponse(Schema):
    request: MentorRequestSchema
    mentor_availability: AvailabilitySchema
    slots: list[datetime]


class AcceptMentorRequestBody(Schema):
    starts_at: datetime
    bring: str = ""


class MentorFeedbackBody(Schema):
    answer: str
    note: str = ""


class MentorProfileSchema(Schema):
    status: str
    weekday_brackets: list[str]
    weekend_brackets: list[str]
    days: list[int]
    classes_per_week: int
    taking_requests: bool
    application_note: str


class MentorTeachingSchema(Schema):
    mentor_class: MentorClassRefSchema
    teacher_status: str
    is_author: bool
    author_name: str
    teacher_count: int


class MentorSettingsResponse(Schema):
    profile: MentorProfileSchema | None
    teaching: list[MentorTeachingSchema]
    invites: list[MentorTeachingSchema]
    joinable: list[MentorClassRefSchema]


class MentorSettingsBody(Schema):
    weekday_brackets: list[str]
    weekend_brackets: list[str]
    days: list[int]
    classes_per_week: int
    taking_requests: bool


class MentorApplyBody(Schema):
    note: str = ""


class RequirementRowSchema(Schema):
    kind: str
    value: str = ""


class MentorClassBody(Schema):
    title: str
    summary: str = ""
    outline: str = ""
    minutes: int = 60
    where: str = "voice"
    requirements: list[RequirementRowSchema] = []
    cover_image_url: str = ""


class MentorClassTeacherSchema(Schema):
    mentor_id: int
    person: MentorPersonSchema
    status: str
    is_author: bool


class RequirementKindSchema(Schema):
    kind: str
    label: str


class MentorClassEditResponse(Schema):
    id: int
    slug: str
    title: str
    summary: str
    outline: str
    minutes: int
    where: str
    requirements: list[RequirementRowSchema]
    cover_image_url: str
    status: str
    review_note: str
    teachers: list[MentorClassTeacherSchema]
    requirement_kinds: list[RequirementKindSchema]
    can_review: bool


class MentorClassCoverSchema(Schema):
    url: str
    label: str


class MentorClassOptionsResponse(Schema):
    covers: list[MentorClassCoverSchema]
    requirement_kinds: list[RequirementKindSchema]


class MentorClassCreatedResponse(Schema):
    id: int
    slug: str


class InviteTeacherBody(Schema):
    character_name: str


class MentorReportSchema(Schema):
    id: int
    pilot: MentorPersonSchema
    mentor: MentorPersonSchema
    class_title: str
    starts_at: datetime | None
    pilot_rating: str
    pilot_rating_label: str
    pilot_note: str
    mentor_outcome: str
    mentor_outcome_label: str
    mentor_notes: str


class AdminMentorClassSchema(Schema):
    id: int
    slug: str
    title: str
    minutes: int
    where: str
    author_name: str
    teachers: list[MentorPersonSchema]
    requests_90d: int
    requirement_count: int
    cover_image_url: str
    status: str
    review_note: str


class AdminMentorSchema(Schema):
    mentor_id: int
    person: MentorPersonSchema
    status: str
    availability: AvailabilitySchema
    classes: int
    taking_requests: bool
    full: bool
    application_note: str


class MentorsAdminResponse(Schema):
    reports: list[MentorReportSchema]
    drafts: list[AdminMentorClassSchema]
    review: list[AdminMentorClassSchema]
    published: list[AdminMentorClassSchema]
    hidden: list[AdminMentorClassSchema]
    applications: list[AdminMentorSchema]
    mentors: list[AdminMentorSchema]


class MentorClassStatusBody(Schema):
    status: str
    note: str = ""


class MentorStatusBody(Schema):
    status: str


class MetricsMentorRowSchema(Schema):
    person: MentorPersonSchema
    availability: AvailabilitySchema
    classes: int
    pilots: int
    answer_hours: float | None
    answer_text: str
    passed: int


class MetricsZoneSchema(Schema):
    code: str
    mentors: list[MentorPersonSchema]
    waiting: int


class MetricsTopicSchema(Schema):
    title: str
    requests: int
    mentors: int
    waiting: int


class MetricsMeasureSchema(Schema):
    label: str
    mentored: float
    similar: float
    percent: bool


class MetricsImpactSchema(Schema):
    name: str
    n: int
    measures: list[MetricsMeasureSchema]


class MentorsMetricsResponse(Schema):
    period_days: int
    requests: int
    pilots: int
    got_mentor_pct: float | None
    first_mentor_pct: float | None
    median_hours_to_booked: float | None
    classes_done: int
    mentors: list[MetricsMentorRowSchema]
    zones: list[MetricsZoneSchema]
    topics: list[MetricsTopicSchema]
    impact: list[MetricsImpactSchema]


class DiscordActionBody(Schema):
    discord_user_id: int


class DiscordFeedbackBody(Schema):
    discord_user_id: int
    answer: str
    note: str = ""


class MentorActionResponse(Schema):
    status: str
    message: str
