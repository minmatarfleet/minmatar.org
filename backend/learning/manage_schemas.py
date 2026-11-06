from ninja import Schema


class ManageLearningSchema(Schema):
    id: int
    slug: str
    title: str
    summary: str
    url: str
    content_kind: str
    thumbnail_url: str
    estimated_minutes: int | None = None
    published: bool


class ManageLearningRequest(Schema):
    slug: str
    title: str
    summary: str = ""
    url: str
    content_kind: str = "guide"
    thumbnail_url: str = ""
    estimated_minutes: int | None = None
    published: bool = True


class ManageCertificateSchema(Schema):
    id: int
    slug: str
    title: str
    summary: str
    published: bool
    sort_order: int
    personas: list[str]
    learning_slugs: list[str]
    award_count: int


class ManageCertificateRequest(Schema):
    slug: str
    title: str
    summary: str = ""
    published: bool = True
    sort_order: int = 0
    personas: list[str] = []
    learning_slugs: list[str] = []


class ManageAwardRequest(Schema):
    username: str
    certificate_slug: str
    reason: str


class ManageAwardResponse(Schema):
    username: str
    certificate_slug: str
    awarded: bool


class ManageOnboardingSchema(Schema):
    program_type: str
    label: str
    version: str
    acknowledgments: int


class ManageSkillLine(Schema):
    name: str
    level: int


class ManageSkillsetSchema(Schema):
    id: int
    name: str
    total_skill_points: int
    skills: list[ManageSkillLine]


class ManageSkillsetRequest(Schema):
    name: str
    skills: list[ManageSkillLine]
    total_skill_points: int | None = None


class ManageSkillSearchResult(Schema):
    name: str
