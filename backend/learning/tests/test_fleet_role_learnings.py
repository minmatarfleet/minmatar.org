"""The Fleet Roles guide and drill learnings seeded by migration 0006."""

import importlib
import re
from pathlib import Path

from django.test import TestCase

from learning.models import Certificate, Learning

migration = importlib.import_module(
    "learning.migrations.0006_seed_fleet_role_learnings"
)

FRONTEND_DATA = (
    Path(__file__).resolve().parents[3] / "frontend/app/src/data/fleet-roles"
)
DRILL = re.compile(r"\{ id: '([a-z0-9-]+)',[^}]*kind: '([a-z]+)'")


class FleetRoleLearningsTestCase(TestCase):
    def test_every_guide_and_drill_is_a_learning(self):
        for role in migration.FLEET_ROLES:
            self.assertTrue(
                Learning.objects.filter(slug=role["guide_slug"]).exists()
            )
            for drill in role["drills"]:
                self.assertTrue(
                    Learning.objects.filter(
                        slug=migration.drill_slug(role["role"], drill[0])
                    ).exists()
                )

    def test_guides_and_drills_point_at_the_guide_page(self):
        guide = Learning.objects.get(slug="damage-guide")
        self.assertEqual(guide.url, "/learning/guides/damage-guide/")
        self.assertEqual(guide.content_kind, "guide")
        drill = Learning.objects.get(
            slug=migration.drill_slug("damage", "fleet-basics-sim")
        )
        self.assertEqual(drill.url, "/learning/guides/damage-guide/#drills")
        self.assertEqual(drill.content_kind, "page")

    def test_the_guides_have_no_certificates(self):
        self.assertFalse(
            Certificate.objects.filter(slug__startswith="fleet-role").exists()
        )

    def test_drills_match_the_frontend_guides(self):
        if not FRONTEND_DATA.exists():
            self.skipTest("needs the full repository checkout")
        for role in migration.FLEET_ROLES:
            source = (FRONTEND_DATA / f"{role['role']}.ts").read_text()
            frontend = [
                drill_id
                for drill_id, kind in DRILL.findall(source)
                if kind != "optional"
            ]
            self.assertEqual(
                frontend,
                [drill[0] for drill in role["drills"]],
                role["role"],
            )
