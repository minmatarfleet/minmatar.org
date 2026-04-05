import re

from django.test import Client
from django.urls import reverse

from app.test import TestCase

from fittings.models import (
    EveDoctrine,
    EveFitting,
    EveFittingHistory,
    EveFittingRefit,
)


class FittingsRouterTestCase(TestCase):
    """Test cases for the fittings router."""

    def setUp(self):
        self.client = Client()

        super().setUp()

    def test_get_doctrines(self):
        EveDoctrine.objects.create(
            name="Test Doctrine",
            type="non_strategic",
            description="A test doctrine",
        )

        response = self.client.get(
            "/api/doctrines/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        doctrines = response.json()
        self.assertEqual(1, len(doctrines))
        self.assertEqual("non_strategic", doctrines[0]["type"])

    def test_get_doctrine_by_id(self):
        doctrine = EveDoctrine.objects.create(
            name="Test Doctrine",
            type="strategic",
            description="A test doctrine",
        )

        response = self.client.get(
            f"/api/doctrines/{doctrine.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        doctrine_data = response.json()
        self.assertEqual("Test Doctrine", doctrine_data["name"])
        self.assertEqual("strategic", doctrine_data["type"])

    def test_get_doctrine_not_found(self):
        response = self.client.get(
            "/api/doctrines/99999",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(404, response.status_code)

    def test_get_fittings(self):
        response = self.client.get(
            "/api/fittings/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        fittings = response.json()
        self.assertEqual(0, len(fittings))

        fitting = EveFitting.objects.create(
            name="[ADV-5] Retribution",
            eft_format="[Retribution, [ADV-5] Retribution]",
            ship_id=608,
        )

        response = self.client.get(
            "/api/fittings/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        fittings = response.json()
        self.assertEqual(1, len(fittings))

        response = self.client.get(
            f"/api/fittings/{fitting.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        fitting = response.json()
        self.assertEqual("[ADV-5] Retribution", fitting["name"])
        self.assertIn("refits", fitting)
        self.assertEqual([], fitting["refits"])
        self.assertIn("tags", fitting)
        self.assertEqual([], fitting["tags"])

    def test_get_fittings_includes_tags_when_set(self):
        EveFitting.objects.create(
            name="[ADV-5] Retribution",
            eft_format="[Retribution, [ADV-5] Retribution]",
            ship_id=608,
            description="",
            tags=["solo", "lowsec"],
        )
        response = self.client.get(
            "/api/fittings/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual(["lowsec", "solo"], data[0]["tags"])

    def test_get_fitting_includes_refits(self):
        fitting = EveFitting.objects.create(
            name="[ADV-5] Retribution",
            eft_format="[Retribution, [ADV-5] Retribution]",
            ship_id=608,
        )
        refit = EveFittingRefit.objects.create(
            base_fitting=fitting,
            name="Scanning refit",
            eft_format="[Retribution, Scanning refit]\n\n[empty high slot]",
        )

        response = self.client.get(
            f"/api/fittings/{fitting.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data["refits"]))
        self.assertEqual(refit.id, data["refits"][0]["id"])
        self.assertEqual("Scanning refit", data["refits"][0]["name"])
        self.assertEqual(refit.eft_format, data["refits"][0]["eft_format"])
        self.assertEqual([], data.get("tags", []))


class EveFittingAdminRefitInlineTestCase(TestCase):
    """Admin: create a refit from the EveFitting change page inline."""

    def setUp(self):
        super().setUp()
        self.make_superuser()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

    def test_add_refit_via_inline(self):
        fitting = EveFitting.objects.create(
            name="[ADV-5] Retribution",
            eft_format="[Retribution, [ADV-5] Retribution]",
            ship_id=608,
            description="Base",
        )
        url = reverse("admin:fittings_evefitting_change", args=[fitting.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        csrf = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            response.content.decode(),
        ).group(1)
        post = {
            "csrfmiddlewaretoken": csrf,
            "name": fitting.name,
            "eft_format": fitting.eft_format,
            "description": fitting.description,
            "aliases": "",
            "minimum_pod": "",
            "recommended_pod": "",
            "refits-TOTAL_FORMS": "1",
            "refits-INITIAL_FORMS": "0",
            "refits-MIN_NUM_FORMS": "0",
            "refits-MAX_NUM_FORMS": "1000",
            "refits-0-name": "Scanning refit",
            "refits-0-eft_format": (
                "[Retribution, Scanning refit]\n\n[empty high slot]"
            ),
            "refits-0-description": "",
            "_save": "Save",
        }
        response = self.client.post(url, post)
        self.assertEqual(
            response.status_code,
            302,
            response.content.decode()[:4000],
        )
        refit = EveFittingRefit.objects.get(base_fitting=fitting)
        self.assertEqual(refit.name, "Scanning refit")
        self.assertEqual(refit.base_fitting_id, fitting.pk)


class EveFittingVersionHistoryTestCase(TestCase):
    """EveFitting latest_version and EveFittingHistory on versioned field changes."""

    def test_create_sets_version_no_history(self):
        fitting = EveFitting.objects.create(
            name="[ADV-5] Retribution",
            eft_format="[Retribution, [ADV-5] Retribution]",
            ship_id=608,
            description="",
        )
        self.assertTrue(fitting.latest_version)
        self.assertEqual(
            0, EveFittingHistory.objects.filter(fitting=fitting).count()
        )

    def test_save_without_versioned_change_preserves_version(self):
        fitting = EveFitting.objects.create(
            name="[ADV-5] Retribution",
            eft_format="[Retribution, [ADV-5] Retribution]",
            ship_id=608,
            description="",
        )
        version_before = fitting.latest_version
        fitting.save()
        fitting.refresh_from_db()
        self.assertEqual(version_before, fitting.latest_version)
        self.assertEqual(
            0, EveFittingHistory.objects.filter(fitting=fitting).count()
        )

    def test_versioned_change_writes_history_and_new_version(self):
        eft_v1 = "[Retribution, [ADV-5] Retribution]"
        eft_v2 = "[Retribution, [ADV-6] Retribution]"
        fitting = EveFitting.objects.create(
            name="[ADV-5] Retribution",
            eft_format=eft_v1,
            ship_id=608,
            description="d1",
        )
        version_v1 = fitting.latest_version

        fitting.name = "[ADV-6] Retribution"
        fitting.eft_format = eft_v2
        fitting.description = "d2"
        fitting.save()

        fitting.refresh_from_db()
        self.assertNotEqual(version_v1, fitting.latest_version)

        history = EveFittingHistory.objects.filter(fitting=fitting)
        self.assertEqual(1, history.count())
        row = history.get()
        self.assertEqual(version_v1, row.superseded_version_id)
        self.assertEqual(eft_v1, row.eft_format)
        self.assertEqual("[ADV-5] Retribution", row.name)
        self.assertEqual(608, row.ship_id)
        self.assertEqual("d1", row.description)
        self.assertEqual([], row.tags)

    def test_tag_change_writes_history_and_new_version(self):
        fitting = EveFitting.objects.create(
            name="[ADV-5] Retribution",
            eft_format="[Retribution, [ADV-5] Retribution]",
            ship_id=608,
            description="d",
            tags=["solo"],
        )
        version_v1 = fitting.latest_version

        fitting.tags = ["solo", "nanogang"]
        fitting.save()

        fitting.refresh_from_db()
        self.assertNotEqual(version_v1, fitting.latest_version)

        history = EveFittingHistory.objects.filter(fitting=fitting)
        self.assertEqual(1, history.count())
        row = history.get()
        self.assertEqual(["solo"], row.tags)
