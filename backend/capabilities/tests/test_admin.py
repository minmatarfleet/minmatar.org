"""The fitting admin page: computed panel, fleet job and skill corrections."""

from django.urls import reverse
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase
from capabilities import services
from capabilities.tests.helpers import fixture_eft, store_fixture_snapshot
from fittings.models import (
    EveDoctrine,
    EveDoctrineFitting,
    EveFitting,
    EveFittingChangeRequest,
    EveFittingHistory,
    EveFittingSkillOverride,
)
from fittings.tests import _empty_fitting_inline_formsets

SIGNATURE_ANALYSIS = 3431


class FittingAdminCapabilitiesTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.make_superuser()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        store_fixture_snapshot()
        category, _ = EveCategory.objects.get_or_create(
            id=16, defaults={"name": "Skill", "published": True}
        )
        group, _ = EveGroup.objects.get_or_create(
            id=1210,
            defaults={
                "name": "Targeting",
                "published": True,
                "eve_category": category,
            },
        )
        self.skill = EveType.objects.create(
            id=SIGNATURE_ANALYSIS,
            name="Signature Analysis",
            published=True,
            eve_group=group,
        )
        eft = fixture_eft("guardian").strip()
        self.fitting = EveFitting.objects.create(
            name=EveFitting.fitting_name_from_eft(eft),
            eft_format=eft,
            ship_id=11987,
            description="Logi",
        )
        doctrine = EveDoctrine.objects.create(
            name="Armor", type="strategic", description=""
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine, fitting=self.fitting, role="primary"
        )
        services.recompute_fitting(self.fitting.pk)
        self.url = reverse(
            "admin:fittings_evefitting_change", args=[self.fitting.pk]
        )

    def _post(self, **extra):
        post = {
            "eft_format": self.fitting.eft_format,
            "description": self.fitting.description,
            "aliases": "",
            "minimum_pod": "",
            "recommended_pod": "",
            "_save": "Save",
            **_empty_fitting_inline_formsets(),
        }
        post.update(extra)
        return self.client.post(self.url, post)

    def test_change_page_shows_computed_requirements(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn("Fleet job &amp; skill requirements", html)
        self.assertIn("Logistics Cruisers", html)
        self.assertIn("Skill corrections", html)

    def test_correction_saves_immediately_and_is_versioned(self):
        version = self.fitting.latest_version
        response = self._post(
            **{
                "skill_overrides-TOTAL_FORMS": "1",
                "skill_overrides-0-skill": SIGNATURE_ANALYSIS,
                "skill_overrides-0-action": "exclude",
                "skill_overrides-0-tier": "core",
                "skill_overrides-0-level": "0",
                "skill_overrides-0-note": "not needed for this fit",
            }
        )
        self.assertEqual(
            response.status_code, 302, response.content.decode()[:3000]
        )
        override = EveFittingSkillOverride.objects.get(fitting=self.fitting)
        self.assertEqual(override.updated_by, self.user)
        self.fitting.refresh_from_db()
        self.assertNotEqual(self.fitting.latest_version, version)
        self.assertTrue(
            EveFittingHistory.objects.filter(
                fitting=self.fitting, superseded_version_id=version
            ).exists()
        )
        self.assertFalse(
            EveFittingChangeRequest.objects.filter(
                fitting=self.fitting
            ).exists()
        )
        rs = services.recompute_fitting(self.fitting.pk)
        self.assertFalse(rs.rows.filter(skill_id=SIGNATURE_ANALYSIS).exists())

    def test_fleet_job_saves_immediately(self):
        response = self._post(capability="Support")
        self.assertEqual(
            response.status_code, 302, response.content.decode()[:3000]
        )
        self.fitting.refresh_from_db()
        self.assertEqual(self.fitting.capability, "Support")
        history = EveFittingHistory.objects.get(fitting=self.fitting)
        self.assertEqual(history.capability, "")

    def test_capabilities_admin_pages_render(self):
        for name in (
            "fittingrequirementset",
            "characterfittingreadiness",
            "charactercapability",
            "sdesnapshot",
            "characteraccount",
            "characteraccountlink",
        ):
            response = self.client.get(
                reverse(f"admin:capabilities_{name}_changelist")
            )
            self.assertEqual(response.status_code, 200, name)
        rs = services.current_set(self.fitting.pk)
        response = self.client.get(
            reverse(
                "admin:capabilities_fittingrequirementset_change", args=[rs.pk]
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Logistics Cruisers", response.content.decode())
