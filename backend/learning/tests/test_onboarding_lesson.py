"""Tests for the Alliance Onboarding lesson seeded by migration 0003."""

import importlib

from django.apps import apps
from django.test import Client, TestCase

from learning.models import Certificate, CertificateLearning, Learning

migration = importlib.import_module(
    "learning.migrations.0003_seed_alliance_onboarding_lesson"
)

EXPECTED_SLUGS = [
    "onboarding-home-base",
    "onboarding-first-fleet",
    "onboarding-fleet-types-and-hangar",
    "onboarding-faction-warfare-essentials",
    "onboarding-first-billion",
    "onboarding-make-content",
    "onboarding-trial-srp-help",
    "onboarding-culture-map",
]


def _lesson_slugs() -> list[str]:
    return list(
        CertificateLearning.objects.filter(
            certificate__slug=migration.CERTIFICATE_SLUG
        )
        .order_by("order")
        .values_list("learning__slug", flat=True)
    )


class OnboardingLessonMigrationTestCase(TestCase):
    def test_lesson_is_published_for_alliance_in_order(self):
        certificate = Certificate.objects.get(slug="alliance-onboarding")
        self.assertTrue(certificate.published)
        self.assertEqual(certificate.personas, ["alliance"])
        self.assertEqual(_lesson_slugs(), EXPECTED_SLUGS)

    def test_learnings_point_at_their_guides(self):
        for slug in EXPECTED_SLUGS:
            learning = Learning.objects.get(slug=slug)
            self.assertEqual(learning.url, f"/learning/guides/{slug}/")
            self.assertEqual(learning.content_kind, "guide")
            self.assertTrue(learning.published)

    def test_lesson_served_by_api(self):
        response = Client().get(
            "/api/learning/certificates/alliance-onboarding"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            [learning["slug"] for learning in data["learnings"]],
            EXPECTED_SLUGS,
        )

    def test_seed_is_idempotent(self):
        migration.seed_onboarding_lesson(apps, None)
        self.assertEqual(_lesson_slugs(), EXPECTED_SLUGS)
        self.assertEqual(
            Learning.objects.filter(slug__in=EXPECTED_SLUGS).count(),
            len(EXPECTED_SLUGS),
        )

    def test_reverse_restores_hidden_placeholder(self):
        for slug, title, url in [
            ("alliance-values", "Alliance Values", "/alliance/values/"),
            (
                "new-player-fleet-guide",
                "New Player Fleet Guide",
                "/learning/guides/new-player-fleet-guide/",
            ),
        ]:
            Learning.objects.create(slug=slug, title=title, url=url)

        migration.unseed_onboarding_lesson(apps, None)

        certificate = Certificate.objects.get(slug="alliance-onboarding")
        self.assertFalse(certificate.published)
        self.assertEqual(certificate.summary, migration.PREVIOUS_SUMMARY)
        self.assertEqual(
            _lesson_slugs(), ["alliance-values", "new-player-fleet-guide"]
        )
        self.assertFalse(
            Learning.objects.filter(slug__in=EXPECTED_SLUGS).exists()
        )
