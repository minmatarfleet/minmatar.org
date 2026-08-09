"""Tests for EveFittingPod models and legacy pod migration."""

import factory

from django.core.exceptions import ValidationError
from django.db.models import signals

from app.test import TestCase
from fittings.endpoints.eve_fittings.serialization import make_fitting_response
from fittings.models import (
    EveFitting,
    EveFittingPod,
    EveFittingTag,
    FittingTag,
)


def _normalize_pod_text(text: str) -> str:
    if not text:
        return ""
    lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
    return "\n".join(lines)


class EveFittingPodTest(TestCase):
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_pod_links_to_fitting(self):
        fitting = EveFitting.objects.create(
            name="Test Fit",
            ship_id=670,
            description="desc",
            eft_format="[Thorax, Test]\n",
        )
        pod = EveFittingPod.objects.create(
            name="Test Fit — Minimum",
            priority=10,
            pod_format="High-grade Snake Alpha",
        )
        fitting.pods.add(pod)
        self.assertEqual(list(fitting.pods.all()), [pod])
        self.assertEqual(list(pod.fittings.all()), [fitting])

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_escape_frigate_validation(self):
        escape_fit = EveFitting.objects.create(
            name="Escape Frig",
            ship_id=670,
            description="desc",
            eft_format="[Slasher, Escape]\n",
        )
        escape_fit.set_tag_slugs(
            [FittingTag.ESCAPE_FRIGATE], write_history=False
        )
        ship_fit = EveFitting.objects.create(
            name="Main Fit",
            ship_id=670,
            description="desc",
            eft_format="[Thorax, Main]\n",
        )
        pod = EveFittingPod.objects.create(
            name="Escape Pod",
            pod_format="Implant A",
        )
        pod.escape_frigate_fittings.add(escape_fit)
        pod.clean()

        pod.escape_frigate_fittings.add(ship_fit)
        with self.assertRaises(ValidationError):
            pod.clean()

    def test_unsaved_pod_clean_skips_m2m(self):
        """Admin add calls full_clean before PK exists (REST-API-M3)."""
        pod = EveFittingPod(name="Unsaved Pod", priority=1, pod_format="A")
        pod.full_clean()


class FittingResponseSerializationTest(TestCase):
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_make_fitting_response_filters_unknown_tags(self):
        """REST-API-M8: stale tag slugs must not 500 the fittings list."""
        fitting = EveFitting.objects.create(
            name="Tagged Fit",
            ship_id=670,
            description="desc",
            eft_format="[Thorax, Test]\n",
            minimum_pod="",
            recommended_pod="",
        )
        fitting.set_tag_slugs(
            [FittingTag.FACTION_WARFARE], write_history=False
        )
        stale, _ = EveFittingTag.objects.get_or_create(
            slug="lowsec",
            defaults={"label": "Lowsec"},
        )
        fitting.tags.add(stale)

        response = make_fitting_response(fitting)

        self.assertIn(FittingTag.FACTION_WARFARE, response.tags)
        self.assertNotIn("lowsec", response.tags)


class LegacyPodMigrationTest(TestCase):
    def test_normalize_pod_text(self):
        self.assertEqual(_normalize_pod_text("A\r\n\r\nB\n"), "A\nB")

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_migration_dedupes_by_pod_format(self):
        fitting_a = EveFitting.objects.create(
            name="Fit A",
            ship_id=670,
            description="desc",
            eft_format="[Thorax, A]\n",
            minimum_pod="Implant One\nImplant Two",
        )
        fitting_b = EveFitting.objects.create(
            name="Fit B",
            ship_id=670,
            description="desc",
            eft_format="[Thorax, B]\n",
            minimum_pod="Implant One\nImplant Two",
        )

        pod_format = _normalize_pod_text("Implant One\nImplant Two")
        pod = EveFittingPod.objects.create(
            name="Shared Pod",
            priority=10,
            pod_format=pod_format,
        )
        fitting_a.pods.add(pod)
        fitting_b.pods.add(pod)

        self.assertEqual(EveFittingPod.objects.count(), 1)
        self.assertEqual(fitting_a.pods.count(), 1)
        self.assertEqual(fitting_b.pods.count(), 1)
