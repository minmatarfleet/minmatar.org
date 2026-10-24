# Seed the Alliance Onboarding lesson: eight guides ordered day one → trial.

from django.db import migrations

CERTIFICATE_SLUG = "alliance-onboarding"

ONBOARDING_SUMMARY = (
    "Start here. Eight short guides in the order you need them: day one "
    "gets you on a fleet, week one sets up your hangar and the warzone, "
    "month one pays for your ships and has you making content, and trial "
    "covers SRP, help, and the rest of the alliance."
)

ONBOARDING_LEARNINGS = [
    {
        "slug": "onboarding-home-base",
        "title": "Home Base: Three Discords and Amamake",
        "summary": (
            "Day one: which Discord is which, how roles work, and why "
            "Amamake is home."
        ),
        "estimated_minutes": 5,
    },
    {
        "slug": "onboarding-first-fleet",
        "title": "Your First Fleet",
        "summary": (
            "Day one: find tonight's fleet, bring what you have, and undock "
            "without panic."
        ),
        "estimated_minutes": 8,
    },
    {
        "slug": "onboarding-fleet-types-and-hangar",
        "title": "Fleet Types and Your Hangar",
        "summary": (
            "Week one: strategic versus everything else, what to keep in "
            "your hangar, and where fits live."
        ),
        "estimated_minutes": 8,
    },
    {
        "slug": "onboarding-faction-warfare-essentials",
        "title": "Faction Warfare Essentials",
        "summary": (
            "Week one: the faction warfare you need to not be lost, written "
            "for returning players."
        ),
        "estimated_minutes": 8,
    },
    {
        "slug": "onboarding-first-billion",
        "title": "Your First Billion ISK",
        "summary": (
            "Month one: plex frontlines, sell LP on the loyalty desk, and "
            "pay for your own ships."
        ),
        "estimated_minutes": 5,
    },
    {
        "slug": "onboarding-make-content",
        "title": "You're Allowed to Make Content",
        "summary": (
            "Month one: form standing fleet, run a battlefield, and schedule "
            "fleets without being a famous FC."
        ),
        "estimated_minutes": 5,
    },
    {
        "slug": "onboarding-trial-srp-help",
        "title": "Trial, SRP, and Getting Help",
        "summary": (
            "Trial: what trial means, how ship replacement works, and where "
            "to take problems."
        ),
        "estimated_minutes": 5,
    },
    {
        "slug": "onboarding-culture-map",
        "title": "The Culture Map",
        "summary": (
            "Trial: town hall, values, tribes, and where the rest of the "
            "alliance lives once you are fleeting."
        ),
        "estimated_minutes": 4,
    },
]

# State the hidden placeholder had before this migration (seed_learning_center).
PREVIOUS_SUMMARY = (
    "Get oriented with our alliance, Minmatar Fleet. Learn about our "
    "values, playstyles, and history."
)
PREVIOUS_LEARNING_SLUGS = [
    "alliance-values",
    "alliance-playstyle",
    "new-player-fleet-guide",
]


def seed_onboarding_lesson(apps, schema_editor):
    Learning = apps.get_model("learning", "Learning")
    Certificate = apps.get_model("learning", "Certificate")
    CertificateLearning = apps.get_model("learning", "CertificateLearning")

    learnings = []
    for fields in ONBOARDING_LEARNINGS:
        learning, _ = Learning.objects.update_or_create(
            slug=fields["slug"],
            defaults={
                "title": fields["title"],
                "summary": fields["summary"],
                "url": f"/learning/guides/{fields['slug']}/",
                "content_kind": "guide",
                "estimated_minutes": fields["estimated_minutes"],
                "published": True,
            },
        )
        learnings.append(learning)

    certificate, _ = Certificate.objects.update_or_create(
        slug=CERTIFICATE_SLUG,
        defaults={
            "title": "Alliance Onboarding",
            "summary": ONBOARDING_SUMMARY,
            "personas": ["alliance"],
            "sort_order": 1,
            "published": True,
        },
    )
    CertificateLearning.objects.filter(certificate=certificate).delete()
    for order, learning in enumerate(learnings):
        CertificateLearning.objects.create(
            certificate=certificate, learning=learning, order=order
        )


def unseed_onboarding_lesson(apps, schema_editor):
    Learning = apps.get_model("learning", "Learning")
    Certificate = apps.get_model("learning", "Certificate")
    CertificateLearning = apps.get_model("learning", "CertificateLearning")

    certificate = Certificate.objects.filter(slug=CERTIFICATE_SLUG).first()
    if certificate is not None:
        certificate.summary = PREVIOUS_SUMMARY
        certificate.published = False
        certificate.save(update_fields=["summary", "published"])
        CertificateLearning.objects.filter(certificate=certificate).delete()
        previous = {
            learning.slug: learning
            for learning in Learning.objects.filter(
                slug__in=PREVIOUS_LEARNING_SLUGS
            )
        }
        for order, slug in enumerate(PREVIOUS_LEARNING_SLUGS):
            if slug in previous:
                CertificateLearning.objects.create(
                    certificate=certificate,
                    learning=previous[slug],
                    order=order,
                )

    Learning.objects.filter(
        slug__in=[fields["slug"] for fields in ONBOARDING_LEARNINGS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("learning", "0002_rewrite_guide_learning_urls"),
    ]

    operations = [
        migrations.RunPython(seed_onboarding_lesson, unseed_onboarding_lesson),
    ]
