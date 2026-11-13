"""Author-facing write endpoints under /api/learning/manage.

Backed by the learning.manage and skillsets.manage pilot features. Every
change writes an audit entry; Django admin stays as break-glass.
"""

import uuid

from django.contrib.auth.models import User
from django.db import transaction
from django.utils.text import slugify
from eveuniverse.models import EveType, EveTypeDogmaAttribute
from ninja import Router

from app.errors import ErrorResponse
from audit.helpers import record_audit
from authentication import AuthBearer
from eveonline.models import EveSkillset
from groups.helpers.feature_access import require_feature
from learning.manage_schemas import (
    ManageAwardRequest,
    ManageAwardResponse,
    ManageCertificateOrderRequest,
    ManageCertificateRequest,
    ManageCertificateSchema,
    ManageLearningRequest,
    ManageLearningSchema,
    ManageOnboardingSchema,
    ManageSkillLine,
    ManageSkillSearchResult,
    ManageSkillsetRequest,
    ManageSkillsetSchema,
)
from learning.models import (
    Certificate,
    CertificateLearning,
    ContentKind,
    Learning,
    Persona,
    UserCertificateAward,
)
from onboarding.models import (
    OnboardingProgram,
    OnboardingProgramType,
    UserOnboardingAcknowledgment,
)

FEATURE_LEARNING = "learning.manage"
FEATURE_SKILLSETS = "skillsets.manage"
SKILL_CATEGORY_ID = 16
ATTR_SKILL_RANK = 275
# Skill points to train one rank of a level (250 * 2^(2.5 * (level - 1))).
LEVEL_POINTS = {1: 250, 2: 1414, 3: 8000, 4: 45255, 5: 256000}

router = Router(tags=["Learning Center management"], auth=AuthBearer())


def _error(detail: str, status: int = 400):
    return status, ErrorResponse(detail=detail)


# --- Guides (Learning) -----------------------------------------------------


def _certificate_steps() -> dict[int, list[tuple[Certificate, int]]]:
    """Learning id -> [(certificate, 1-based step)], certificates in
    their own order. One query."""
    steps: dict[int, list[tuple[Certificate, int]]] = {}
    links = CertificateLearning.objects.select_related("certificate").order_by(
        "certificate__sort_order", "certificate__title", "order", "id"
    )
    positions: dict[int, int] = {}
    for link in links:
        positions[link.certificate_id] = (
            positions.get(link.certificate_id, 0) + 1
        )
        steps.setdefault(link.learning_id, []).append(
            (link.certificate, positions[link.certificate_id])
        )
    return steps


def _guide_schema(
    item: Learning,
    steps: dict[int, list[tuple[Certificate, int]]] | None = None,
) -> ManageLearningSchema:
    if steps is None:
        steps = _certificate_steps()
    memberships = steps.get(item.pk, [])
    first = memberships[0] if memberships else None
    return ManageLearningSchema(
        certificate_slug=first[0].slug if first else "",
        certificate_title=first[0].title if first else "",
        certificate_step=first[1] if first else None,
        certificate_count=len(memberships),
        id=item.pk,
        slug=item.slug,
        title=item.title,
        summary=item.summary,
        url=item.url,
        content_kind=item.content_kind,
        thumbnail_url=item.thumbnail_url,
        estimated_minutes=item.estimated_minutes,
        published=item.published,
    )


def _validate_guide(payload: ManageLearningRequest) -> str | None:
    if not payload.title.strip():
        return "Title is required."
    if not payload.url.strip():
        return "URL is required."
    if not payload.slug or slugify(payload.slug) != payload.slug:
        return "Slug must be lowercase letters, numbers and dashes."
    if payload.content_kind not in ContentKind.values:
        return "Unknown content kind."
    if payload.content_kind == ContentKind.MENTOR_CLASS:
        return "Mentor classes are made in the mentor class editor."
    return None


def _apply_guide(item: Learning, payload: ManageLearningRequest) -> None:
    item.slug = payload.slug
    item.title = payload.title.strip()
    item.summary = payload.summary
    item.url = payload.url.strip()
    item.content_kind = payload.content_kind
    item.thumbnail_url = payload.thumbnail_url
    item.estimated_minutes = payload.estimated_minutes
    item.published = payload.published
    item.save()


@router.get(
    "guides",
    response={200: list[ManageLearningSchema], 403: dict},
    summary="List every learning guide, published or not.",
)
def list_guides(request):
    if denied := require_feature(request.user, FEATURE_LEARNING):
        return denied
    steps = _certificate_steps()
    return [_guide_schema(i, steps) for i in Learning.objects.all()]


@router.post(
    "guides",
    response={200: ManageLearningSchema, 400: ErrorResponse, 403: dict},
    summary="Create a learning guide.",
)
def create_guide(request, payload: ManageLearningRequest):
    if denied := require_feature(request.user, FEATURE_LEARNING):
        return denied
    if message := _validate_guide(payload):
        return _error(message)
    if Learning.objects.filter(slug=payload.slug).exists():
        return _error("That slug is taken.")
    item = Learning()
    _apply_guide(item, payload)
    record_audit(request.user, f"Created learning guide {item.slug}")
    return _guide_schema(item)


@router.put(
    "guides/{slug}",
    response={
        200: ManageLearningSchema,
        400: ErrorResponse,
        403: dict,
        404: ErrorResponse,
    },
    summary="Edit a learning guide.",
)
def update_guide(request, slug: str, payload: ManageLearningRequest):
    if denied := require_feature(request.user, FEATURE_LEARNING):
        return denied
    item = Learning.objects.filter(slug=slug).first()
    if item is None:
        return _error("Guide not found.", 404)
    if item.content_kind == ContentKind.MENTOR_CLASS:
        # The mentor class owns this row (title, URL, published) and
        # rewrites it on every save.
        return _error("Edit this in the mentor class editor.")
    if message := _validate_guide(payload):
        return _error(message)
    if (
        payload.slug != slug
        and Learning.objects.filter(slug=payload.slug).exists()
    ):
        return _error("That slug is taken.")
    _apply_guide(item, payload)
    record_audit(request.user, f"Edited learning guide {item.slug}")
    return _guide_schema(item)


# --- Certificates ----------------------------------------------------------


def _certificate_schema(cert: Certificate) -> ManageCertificateSchema:
    return ManageCertificateSchema(
        id=cert.pk,
        slug=cert.slug,
        title=cert.title,
        summary=cert.summary,
        published=cert.published,
        sort_order=cert.sort_order,
        personas=list(cert.personas or []),
        learning_slugs=[
            link.learning.slug
            for link in cert.certificate_learnings.select_related("learning")
        ],
        award_count=cert.awards.count(),
    )


def _validate_certificate(payload: ManageCertificateRequest) -> str | None:
    if not payload.title.strip():
        return "Title is required."
    if not payload.slug or slugify(payload.slug) != payload.slug:
        return "Slug must be lowercase letters, numbers and dashes."
    if any(p not in Persona.values for p in payload.personas):
        return "Unknown persona."
    known = set(
        Learning.objects.filter(slug__in=payload.learning_slugs).values_list(
            "slug", flat=True
        )
    )
    if missing := [s for s in payload.learning_slugs if s not in known]:
        return f"Unknown guide: {missing[0]}."
    if len(set(payload.learning_slugs)) != len(payload.learning_slugs):
        return "A guide is listed twice."
    return None


@transaction.atomic
def _apply_certificate(
    cert: Certificate, payload: ManageCertificateRequest
) -> None:
    cert.slug = payload.slug
    cert.title = payload.title.strip()
    cert.summary = payload.summary
    cert.published = payload.published
    cert.sort_order = payload.sort_order
    cert.personas = list(payload.personas)
    cert.save()
    cert.certificate_learnings.all().delete()
    by_slug = {
        i.slug: i
        for i in Learning.objects.filter(slug__in=payload.learning_slugs)
    }
    CertificateLearning.objects.bulk_create(
        CertificateLearning(
            certificate=cert, learning=by_slug[slug], order=index
        )
        for index, slug in enumerate(payload.learning_slugs)
    )


@router.get(
    "certificates",
    response={200: list[ManageCertificateSchema], 403: dict},
    summary="List every certificate, published or not.",
)
def list_certificates(request):
    if denied := require_feature(request.user, FEATURE_LEARNING):
        return denied
    return [_certificate_schema(c) for c in Certificate.objects.all()]


@router.post(
    "certificates",
    response={200: ManageCertificateSchema, 400: ErrorResponse, 403: dict},
    summary="Create a certificate.",
)
def create_certificate(request, payload: ManageCertificateRequest):
    if denied := require_feature(request.user, FEATURE_LEARNING):
        return denied
    if message := _validate_certificate(payload):
        return _error(message)
    if Certificate.objects.filter(slug=payload.slug).exists():
        return _error("That slug is taken.")
    cert = Certificate()
    _apply_certificate(cert, payload)
    record_audit(request.user, f"Created certificate {cert.slug}")
    return _certificate_schema(cert)


@router.post(
    "certificates/order",
    response={
        200: list[ManageCertificateSchema],
        400: ErrorResponse,
        403: dict,
    },
    summary="Put certificates in this order (the slugs, first to last).",
)
def order_certificates(request, payload: ManageCertificateOrderRequest):
    if denied := require_feature(request.user, FEATURE_LEARNING):
        return denied
    by_slug = {c.slug: c for c in Certificate.objects.all()}
    if len(set(payload.slugs)) != len(payload.slugs):
        return _error("A certificate is listed twice.")
    if missing := [s for s in payload.slugs if s not in by_slug]:
        return _error(f"Certificate not found: {missing[0]}.")
    # Certificates left out keep their relative order after the listed ones.
    rest = [c for c in by_slug.values() if c.slug not in payload.slugs]
    ordered = [by_slug[s] for s in payload.slugs] + sorted(
        rest, key=lambda c: (c.sort_order, c.title)
    )
    changed = []
    for index, cert in enumerate(ordered, start=1):
        if cert.sort_order != index:
            cert.sort_order = index
            changed.append(cert)
    if changed:
        Certificate.objects.bulk_update(changed, ["sort_order"])
        record_audit(
            request.user,
            "Reordered certificates: " + ", ".join(c.slug for c in ordered),
        )
    return [_certificate_schema(c) for c in Certificate.objects.all()]


@router.put(
    "certificates/{slug}",
    response={
        200: ManageCertificateSchema,
        400: ErrorResponse,
        403: dict,
        404: ErrorResponse,
    },
    summary="Edit a certificate and its ordered guides.",
)
def update_certificate(request, slug: str, payload: ManageCertificateRequest):
    if denied := require_feature(request.user, FEATURE_LEARNING):
        return denied
    cert = Certificate.objects.filter(slug=slug).first()
    if cert is None:
        return _error("Certificate not found.", 404)
    if message := _validate_certificate(payload):
        return _error(message)
    if (
        payload.slug != slug
        and Certificate.objects.filter(slug=payload.slug).exists()
    ):
        return _error("That slug is taken.")
    _apply_certificate(cert, payload)
    record_audit(request.user, f"Edited certificate {cert.slug}")
    return _certificate_schema(cert)


def _change_award(request, payload: ManageAwardRequest, *, award: bool):
    if denied := require_feature(request.user, FEATURE_LEARNING):
        return denied
    reason = payload.reason.strip()
    if not reason:
        return _error("A reason is required.")
    user = User.objects.filter(
        username__iexact=payload.username.strip()
    ).first()
    if user is None:
        return _error("No such user.", 404)
    cert = Certificate.objects.filter(slug=payload.certificate_slug).first()
    if cert is None:
        return _error("Certificate not found.", 404)
    if award:
        UserCertificateAward.objects.get_or_create(user=user, certificate=cert)
        verb = "Awarded"
    else:
        UserCertificateAward.objects.filter(
            user=user, certificate=cert
        ).delete()
        verb = "Revoked"
    record_audit(
        request.user,
        f"{verb} certificate {cert.slug} "
        f"{'to' if award else 'from'} {user.username}: {reason}",
    )
    return ManageAwardResponse(
        username=user.username, certificate_slug=cert.slug, awarded=award
    )


@router.post(
    "awards",
    response={
        200: ManageAwardResponse,
        400: ErrorResponse,
        403: dict,
        404: ErrorResponse,
    },
    summary="Award a certificate by hand, with a reason.",
)
def award_certificate(request, payload: ManageAwardRequest):
    return _change_award(request, payload, award=True)


@router.post(
    "awards/revoke",
    response={
        200: ManageAwardResponse,
        400: ErrorResponse,
        403: dict,
        404: ErrorResponse,
    },
    summary="Revoke a certificate by hand, with a reason.",
)
def revoke_certificate(request, payload: ManageAwardRequest):
    return _change_award(request, payload, award=False)


# --- Onboarding programs ---------------------------------------------------


def _onboarding_schema(program: OnboardingProgram) -> ManageOnboardingSchema:
    return ManageOnboardingSchema(
        program_type=program.program_type,
        label=OnboardingProgramType(program.program_type).label,
        version=str(program.version),
        acknowledgments=UserOnboardingAcknowledgment.objects.filter(
            program=program, acknowledged_version=program.version
        ).count(),
    )


@router.get(
    "onboarding",
    response={200: list[ManageOnboardingSchema], 403: dict},
    summary="List onboarding programs with their current version.",
)
def list_onboarding(request):
    if denied := require_feature(request.user, FEATURE_LEARNING):
        return denied
    programs = []
    for value in OnboardingProgramType.values:
        program, _ = OnboardingProgram.objects.get_or_create(
            program_type=value
        )
        programs.append(_onboarding_schema(program))
    return programs


@router.post(
    "onboarding/{program_type}/version",
    response={200: ManageOnboardingSchema, 403: dict, 404: ErrorResponse},
    summary="Bump a program's version so every pilot acknowledges it again.",
)
def bump_onboarding(request, program_type: str):
    if denied := require_feature(request.user, FEATURE_LEARNING):
        return denied
    if program_type not in OnboardingProgramType.values:
        return _error("Program not found.", 404)
    program, _ = OnboardingProgram.objects.get_or_create(
        program_type=program_type
    )
    program.version = uuid.uuid4()
    program.save(update_fields=["version"])
    record_audit(
        request.user, f"Bumped onboarding program {program_type} version"
    )
    return _onboarding_schema(program)


# --- Skillsets -------------------------------------------------------------


def _parse_skills(text: str) -> list[ManageSkillLine]:
    lines = []
    for raw in (text or "").split("\n"):
        name, _, level = raw.strip().rpartition(" ")
        if name and level.isdigit():
            lines.append(ManageSkillLine(name=name, level=int(level)))
    return lines


def _skillset_schema(skillset: EveSkillset) -> ManageSkillsetSchema:
    return ManageSkillsetSchema(
        id=skillset.pk,
        name=skillset.name,
        total_skill_points=skillset.total_skill_points,
        skills=_parse_skills(skillset.skills),
    )


def _skill_points(lines: list[ManageSkillLine]) -> int:
    ranks = {
        row.eve_type.name: row.value
        for row in EveTypeDogmaAttribute.objects.filter(
            dogma_attribute_id=ATTR_SKILL_RANK,
            eve_type__name__in=[line.name for line in lines],
        ).select_related("eve_type")
    }
    return int(
        sum(
            LEVEL_POINTS[line.level] * ranks.get(line.name, 1)
            for line in lines
        )
    )


def _validate_skillset(payload: ManageSkillsetRequest) -> str | None:
    if not payload.name.strip():
        return "Name is required."
    if not payload.skills:
        return "Pick at least one skill."
    if any(line.level not in LEVEL_POINTS for line in payload.skills):
        return "Skill levels run from 1 to 5."
    names = [line.name for line in payload.skills]
    if len(set(names)) != len(names):
        return "A skill is listed twice."
    known = set(
        EveType.objects.filter(
            eve_group__eve_category_id=SKILL_CATEGORY_ID, name__in=names
        ).values_list("name", flat=True)
    )
    if missing := [n for n in names if n not in known]:
        return f"Unknown skill: {missing[0]}."
    return None


def _apply_skillset(skillset: EveSkillset, payload: ManageSkillsetRequest):
    skillset.name = payload.name.strip()
    skillset.skills = "\n".join(
        f"{line.name} {line.level}" for line in payload.skills
    )
    skillset.total_skill_points = (
        payload.total_skill_points
        if payload.total_skill_points is not None
        else _skill_points(payload.skills)
    )
    skillset.save()


@router.get(
    "skillsets",
    response={200: list[ManageSkillsetSchema], 403: dict},
    summary="List skillsets with their skills and levels.",
)
def list_skillsets(request):
    if denied := require_feature(request.user, FEATURE_SKILLSETS):
        return denied
    return [_skillset_schema(s) for s in EveSkillset.objects.order_by("name")]


@router.get(
    "skillsets/skill-search",
    response={200: list[ManageSkillSearchResult], 403: dict},
    summary="Typeahead over skill names.",
)
def search_skills(request, q: str = ""):
    if denied := require_feature(request.user, FEATURE_SKILLSETS):
        return denied
    q = q.strip()
    if len(q) < 2:
        return []
    names = (
        EveType.objects.filter(
            eve_group__eve_category_id=SKILL_CATEGORY_ID,
            published=True,
            name__icontains=q,
        )
        .order_by("name")
        .values_list("name", flat=True)[:15]
    )
    return [ManageSkillSearchResult(name=n) for n in names]


@router.post(
    "skillsets",
    response={200: ManageSkillsetSchema, 400: ErrorResponse, 403: dict},
    summary="Create a skillset.",
)
def create_skillset(request, payload: ManageSkillsetRequest):
    if denied := require_feature(request.user, FEATURE_SKILLSETS):
        return denied
    if message := _validate_skillset(payload):
        return _error(message)
    skillset = EveSkillset()
    _apply_skillset(skillset, payload)
    record_audit(request.user, f"Created skillset {skillset.name}")
    return _skillset_schema(skillset)


@router.put(
    "skillsets/{skillset_id}",
    response={
        200: ManageSkillsetSchema,
        400: ErrorResponse,
        403: dict,
        404: ErrorResponse,
    },
    summary="Edit a skillset.",
)
def update_skillset(request, skillset_id: int, payload: ManageSkillsetRequest):
    if denied := require_feature(request.user, FEATURE_SKILLSETS):
        return denied
    skillset = EveSkillset.objects.filter(pk=skillset_id).first()
    if skillset is None:
        return _error("Skillset not found.", 404)
    if message := _validate_skillset(payload):
        return _error(message)
    _apply_skillset(skillset, payload)
    record_audit(request.user, f"Edited skillset {skillset.name}")
    return _skillset_schema(skillset)
