"""Shared helpers for Learning Center awards, persona, and import."""

from django.utils import timezone

from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCorporation
from learning.models import (
    Certificate,
    CertificateLearning,
    Learning,
    Persona,
    UserCertificateAward,
    UserLearningPreference,
    UserLearningProgress,
)

PERSONA_REASON_ALLIANCE = "learning.persona.reason.alliance"
PERSONA_REASON_MILITIA = "learning.persona.reason.militia"
PERSONA_REASON_OTHER = "learning.persona.reason.other"

MAX_IMPORT_LEARNINGS = 200


def recommend_persona(user) -> dict:
    """
    Suggest a persona from the user's primary character corporation type.

    Returns dict with keys: persona, reason_key, corp_type.
    """
    primary = user_primary_character(user)
    if primary is None or not primary.corporation_id:
        return {
            "persona": Persona.OTHER,
            "reason_key": PERSONA_REASON_OTHER,
            "corp_type": None,
        }

    corp = EveCorporation.objects.filter(
        corporation_id=primary.corporation_id
    ).first()
    if corp is None:
        return {
            "persona": Persona.OTHER,
            "reason_key": PERSONA_REASON_OTHER,
            "corp_type": None,
        }

    corp_type = corp.type
    if corp_type in ("alliance", "associate"):
        return {
            "persona": Persona.ALLIANCE,
            "reason_key": PERSONA_REASON_ALLIANCE,
            "corp_type": corp_type,
        }
    if corp_type == "militia":
        return {
            "persona": Persona.MILITIA,
            "reason_key": PERSONA_REASON_MILITIA,
            "corp_type": corp_type,
        }
    return {
        "persona": Persona.OTHER,
        "reason_key": PERSONA_REASON_OTHER,
        "corp_type": corp_type,
    }


def set_persona(
    user, persona: str, *, confirmed: bool = True
) -> UserLearningPreference:
    if persona not in Persona.values:
        raise ValueError(f"Invalid persona: {persona}")

    pref, _ = UserLearningPreference.objects.get_or_create(user=user)
    pref.persona = persona
    update_fields = ["persona", "updated_at"]
    if confirmed:
        pref.persona_confirmed_at = timezone.now()
        update_fields.append("persona_confirmed_at")
    pref.save(update_fields=update_fields)
    return pref


def completed_learning_ids(user) -> set[int]:
    return set(
        UserLearningProgress.objects.filter(user=user).values_list(
            "learning_id", flat=True
        )
    )


def completed_learning_slugs(user) -> list[str]:
    return list(
        UserLearningProgress.objects.filter(user=user)
        .select_related("learning")
        .order_by("completed_at")
        .values_list("learning__slug", flat=True)
    )


def mark_learning_complete(
    user, learning: Learning
) -> tuple[UserLearningProgress, bool, list[UserCertificateAward]]:
    progress, created = UserLearningProgress.objects.get_or_create(
        user=user,
        learning=learning,
    )
    awarded: list[UserCertificateAward] = []
    if created:
        awarded = recompute_awards_for_user(user, learning_ids={learning.pk})
    return progress, created, awarded


def certificate_published_learning_ids(certificate: Certificate) -> list[int]:
    """Published learnings only — same set serialize_certificate exposes to the API."""
    return list(
        CertificateLearning.objects.filter(
            certificate=certificate,
            learning__published=True,
        )
        .order_by("order", "id")
        .values_list("learning_id", flat=True)
    )


def recompute_awards_for_user(
    user, learning_ids: set[int] | None = None
) -> list[UserCertificateAward]:
    """
    Award any published certificates whose published learnings are all completed.

    Unpublished learnings linked to a certificate are ignored (same as API
    serialization). If learning_ids is provided, only certificates that include
    those learnings are checked (performance for single completions).
    """
    cert_qs = Certificate.objects.filter(published=True)
    if learning_ids:
        cert_qs = cert_qs.filter(learnings__id__in=learning_ids).distinct()

    completed = completed_learning_ids(user)
    awarded: list[UserCertificateAward] = []

    for certificate in cert_qs.prefetch_related(
        "certificate_learnings__learning"
    ):
        required = set(certificate_published_learning_ids(certificate))
        if not required:
            continue
        if not required.issubset(completed):
            continue
        award, created = UserCertificateAward.objects.get_or_create(
            user=user,
            certificate=certificate,
        )
        if created:
            awarded.append(award)

    return awarded


def import_learning_progress(
    *,
    user,
    completed_slugs: list[str] | None = None,
    persona: str | None = None,
) -> dict:
    """
    Union-merge anonymous completions (and optional persona) into the user.

    Never removes existing server progress.
    """
    slugs: list[str] = []
    seen: set[str] = set()
    for raw in completed_slugs or []:
        slug = (raw or "").strip()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        slugs.append(slug)
        if len(slugs) >= MAX_IMPORT_LEARNINGS:
            break

    learnings = {
        learning.slug: learning
        for learning in Learning.objects.filter(slug__in=slugs, published=True)
    }
    newly_completed: list[str] = []
    for slug in slugs:
        learning = learnings.get(slug)
        if learning is None:
            continue
        _, created, _ = mark_learning_complete(user, learning)
        if created:
            newly_completed.append(slug)

    persona_set = None
    if persona and persona in Persona.values:
        pref = UserLearningPreference.objects.filter(user=user).first()
        if pref is None or pref.persona_confirmed_at is None:
            set_persona(user, persona, confirmed=True)
            persona_set = persona

    awards = list(
        UserCertificateAward.objects.filter(user=user)
        .select_related("certificate")
        .order_by("awarded_at")
    )

    return {
        "imported_slugs": newly_completed,
        "persona": persona_set,
        "awards": awards,
        "completed_slugs": completed_learning_slugs(user),
    }


def certificates_for_persona(persona: str | None) -> list[Certificate]:
    qs = (
        Certificate.objects.filter(published=True)
        .prefetch_related("certificate_learnings__learning")
        .order_by("sort_order", "title")
    )
    certificates = list(qs)
    if not persona:
        return certificates
    return [c for c in certificates if persona in (c.personas or [])]
