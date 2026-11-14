"""The Fleet Roles certificates seeded by migration 0006."""

import importlib
import re
from pathlib import Path

from django.test import Client, TestCase

from learning.models import Certificate, CertificateLearning, Learning

migration = importlib.import_module(
    "learning.migrations.0006_seed_fleet_role_certificates"
)

FRONTEND_DATA = (
    Path(__file__).resolve().parents[3] / "frontend/app/src/data/fleet-roles"
)
DRILL = re.compile(r"\{ id: '([a-z0-9-]+)',[^}]*kind: '([a-z]+)'")


def _slugs(certificate_slug: str) -> list[str]:
    return list(
        CertificateLearning.objects.filter(certificate__slug=certificate_slug)
        .order_by("order")
        .values_list("learning__slug", flat=True)
    )


class FleetRoleCertificatesTestCase(TestCase):
    def test_one_certificate_per_role_with_the_guide_first(self):
        for role in migration.FLEET_ROLES:
            slug = migration.certificate_slug(role["role"])
            certificate = Certificate.objects.get(slug=slug)
            self.assertTrue(certificate.published)
            self.assertEqual(certificate.personas, ["alliance", "militia"])
            self.assertEqual(
                _slugs(slug),
                [role["guide_slug"]]
                + [
                    migration.drill_slug(role["role"], drill[0])
                    for drill in role["drills"]
                ],
            )

    def test_guides_and_drills_point_at_the_guide_page(self):
        role = migration.FLEET_ROLES[0]
        guide = Learning.objects.get(slug=role["guide_slug"])
        self.assertEqual(guide.url, "/learning/guides/damage-guide/")
        self.assertEqual(guide.content_kind, "guide")
        drill = Learning.objects.get(
            slug=migration.drill_slug("damage", "applied-sim")
        )
        self.assertEqual(drill.url, "/learning/guides/damage-guide/#drills")
        self.assertEqual(drill.content_kind, "page")

    def test_served_by_api(self):
        response = Client().get(
            "/api/learning/certificates/fleet-role-remote-repair"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Remote Repair")

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
