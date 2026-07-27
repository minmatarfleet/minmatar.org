from learning.models import Certificate, Learning
from learning.schemas import (
    CertificateAwardSchema,
    CertificateSchema,
    LearningSchema,
)


def serialize_learning(
    learning: Learning,
    *,
    order: int = 0,
) -> LearningSchema:
    return LearningSchema(
        slug=learning.slug,
        title=learning.title,
        summary=learning.summary or "",
        url=learning.url,
        content_kind=learning.content_kind,
        thumbnail_url=learning.thumbnail_url or "",
        estimated_minutes=learning.estimated_minutes,
        order=order,
    )


def serialize_certificate(certificate: Certificate) -> CertificateSchema:
    links = sorted(
        certificate.certificate_learnings.all(),
        key=lambda link: (link.order, link.pk),
    )
    learnings = [
        serialize_learning(link.learning, order=link.order)
        for link in links
        if link.learning.published
    ]
    return CertificateSchema(
        slug=certificate.slug,
        title=certificate.title,
        summary=certificate.summary or "",
        sort_order=certificate.sort_order,
        personas=list(certificate.personas or []),
        learnings=learnings,
        learning_count=len(learnings),
    )


def serialize_award(award) -> CertificateAwardSchema:
    return CertificateAwardSchema(
        slug=award.certificate.slug,
        title=award.certificate.title,
        awarded_at=award.awarded_at.isoformat(),
    )


def get_published_certificate(slug: str) -> Certificate | None:
    return (
        Certificate.objects.filter(slug=slug, published=True)
        .prefetch_related("certificate_learnings__learning")
        .first()
    )
