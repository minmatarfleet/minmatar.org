from ninja import Schema


class LearningSchema(Schema):
    slug: str
    title: str
    summary: str
    url: str
    content_kind: str
    thumbnail_url: str = ""
    estimated_minutes: int | None = None
    order: int = 0


class CertificateSchema(Schema):
    slug: str
    title: str
    summary: str
    sort_order: int
    personas: list[str]
    learnings: list[LearningSchema]
    learning_count: int


class CertificateAwardSchema(Schema):
    slug: str
    title: str
    awarded_at: str


class PersonaRecommendationSchema(Schema):
    persona: str
    reason_key: str
    corp_type: str | None = None


class PersonaRequest(Schema):
    persona: str


class PersonaResponse(Schema):
    persona: str
    confirmed: bool


class MeResponse(Schema):
    persona: str | None = None
    persona_confirmed: bool = False
    completed_learning_slugs: list[str]
    awards: list[CertificateAwardSchema]


class CompleteLearningResponse(Schema):
    learning_slug: str
    completed: bool
    newly_awarded: list[CertificateAwardSchema]


class ImportRequest(Schema):
    completed_learning_slugs: list[str] = []
    persona: str | None = None


class ImportResponse(Schema):
    imported_slugs: list[str]
    persona: str | None = None
    completed_learning_slugs: list[str]
    awards: list[CertificateAwardSchema]
