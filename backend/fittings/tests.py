import re

from django.db import IntegrityError
from django.test import Client
from django.urls import reverse

from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase

from fittings.models import (
    EveDoctrine,
    EveFitting,
    EveFittingChangeRequest,
    EveFittingHistory,
    EveFittingModuleSubstitution,
    EveFittingRefit,
)


def _empty_fitting_inline_formsets(**overrides):
    """Management form fields for EveFittingAdmin inlines."""
    data = {
        "refits-TOTAL_FORMS": "0",
        "refits-INITIAL_FORMS": "0",
        "refits-MIN_NUM_FORMS": "0",
        "refits-MAX_NUM_FORMS": "1000",
        "module_substitutions-TOTAL_FORMS": "0",
        "module_substitutions-INITIAL_FORMS": "0",
        "module_substitutions-MIN_NUM_FORMS": "0",
        "module_substitutions-MAX_NUM_FORMS": "1000",
    }
    data.update(overrides)
    return data


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
        self.assertIn("known_key", fitting)
        self.assertIsNone(fitting["known_key"])

    def test_get_fittings_includes_known_key_when_set(self):
        fitting = EveFitting.objects.create(
            name="[ADV-5] Retribution",
            eft_format="[Retribution, [ADV-5] Retribution]",
            ship_id=608,
            description="",
            known_key="guide.fw-cruiser.omen-kite-pulse",
        )
        response = self.client.get(
            "/api/fittings/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual(
            "guide.fw-cruiser.omen-kite-pulse", data[0]["known_key"]
        )
        self.assertEqual(fitting.id, data[0]["id"])

    def test_known_key_unique_among_active_fittings(self):
        EveFitting.objects.create(
            name="Pulse Omen A",
            eft_format="[Omen, Pulse Omen A]",
            ship_id=2006,
            description="",
            known_key="guide.fw-cruiser.omen-kite-pulse",
        )
        duplicate = EveFitting(
            name="Pulse Omen B",
            eft_format="[Omen, Pulse Omen B]",
            ship_id=2006,
            description="",
            known_key="guide.fw-cruiser.omen-kite-pulse",
        )
        with self.assertRaises(IntegrityError):
            duplicate.save()

    def test_get_fittings_includes_tags_when_set(self):
        fitting = EveFitting.objects.create(
            name="[ADV-5] Retribution",
            eft_format="[Retribution, [ADV-5] Retribution]",
            ship_id=608,
            description="",
        )
        fitting.set_tag_slugs(["nanogang", "nullsec"], write_history=False)
        response = self.client.get(
            "/api/fittings/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual(["nanogang", "nullsec"], data[0]["tags"])

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
        html = response.content.decode()
        self.assertIn("cannot be edited separately", html)
        csrf = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            html,
        ).group(1)
        post = {
            "csrfmiddlewaretoken": csrf,
            "eft_format": fitting.eft_format,
            "description": fitting.description,
            "aliases": "",
            "minimum_pod": "",
            "recommended_pod": "",
            **_empty_fitting_inline_formsets(
                **{
                    "refits-TOTAL_FORMS": "1",
                    "refits-0-eft_format": (
                        "[Retribution, Scanning refit]\n\n[empty high slot]"
                    ),
                    "refits-0-description": "",
                }
            ),
            "_save": "Save",
        }
        response = self.client.post(url, post)
        self.assertEqual(
            response.status_code,
            302,
            response.content.decode()[:4000],
        )
        self.assertFalse(
            EveFittingRefit.objects.filter(base_fitting=fitting).exists()
        )
        req = EveFittingChangeRequest.objects.get(fitting=fitting)
        self.assertEqual("refit_create", req.change_kind)
        self.assertEqual("Scanning refit", req.payload["name"])

    def test_eft_change_queues_change_request(self):
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
        new_eft = "[Retribution, [ADV-5] Retribution v2]"
        post = {
            "csrfmiddlewaretoken": csrf,
            "eft_format": new_eft,
            "description": fitting.description,
            "aliases": "",
            "minimum_pod": "",
            "recommended_pod": "",
            **_empty_fitting_inline_formsets(),
            "_save": "Save",
        }
        response = self.client.post(url, post)
        self.assertEqual(
            response.status_code,
            302,
            response.content.decode()[:4000],
        )
        fitting.refresh_from_db()
        self.assertEqual(
            "[Retribution, [ADV-5] Retribution]",
            fitting.eft_format,
        )
        self.assertEqual("[ADV-5] Retribution", fitting.name)
        req = EveFittingChangeRequest.objects.get(fitting=fitting)
        self.assertEqual("fitting_versioned", req.change_kind)
        self.assertEqual(new_eft, req.payload["eft_format"])

    def test_mismatched_name_syncs_from_eft_without_approval(self):
        fitting = EveFitting.objects.create(
            name="Legacy display name",
            eft_format="[Retribution, [ADV-5] Retribution]",
            ship_id=608,
            description="Base",
        )
        url = reverse("admin:fittings_evefitting_change", args=[fitting.pk])
        response = self.client.get(url)
        csrf = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            response.content.decode(),
        ).group(1)
        post = {
            "csrfmiddlewaretoken": csrf,
            "eft_format": fitting.eft_format,
            "description": fitting.description,
            "aliases": "",
            "minimum_pod": "",
            "recommended_pod": "",
            **_empty_fitting_inline_formsets(),
            "_save": "Save",
        }
        response = self.client.post(url, post)
        self.assertEqual(response.status_code, 302)
        fitting.refresh_from_db()
        self.assertEqual("[ADV-5] Retribution", fitting.name)
        self.assertFalse(
            EveFittingChangeRequest.objects.filter(fitting=fitting).exists()
        )


class EveFittingAdminCreateDeleteApprovalTestCase(TestCase):
    """Admin create/delete queue fitting change requests."""

    def setUp(self):
        super().setUp()
        self.make_superuser()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        category, _ = EveCategory.objects.get_or_create(
            id=6,
            defaults={"name": "Ship", "published": True},
        )
        group, _ = EveGroup.objects.get_or_create(
            id=25,
            defaults={
                "name": "Frigate",
                "eve_category": category,
                "published": True,
            },
        )
        EveType.objects.get_or_create(
            id=587,
            defaults={
                "name": "Rifter",
                "eve_group": group,
                "published": True,
            },
        )

    def test_add_queues_fitting_create(self):
        url = reverse("admin:fittings_evefitting_add")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        csrf = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            response.content.decode(),
        ).group(1)
        post = {
            "csrfmiddlewaretoken": csrf,
            "eft_format": "[Rifter, [TEST] New Fit]",
            "description": "brand new",
            "aliases": "",
            "minimum_pod": "",
            "recommended_pod": "",
            **_empty_fitting_inline_formsets(),
            "_save": "Save",
        }
        response = self.client.post(url, post)
        self.assertEqual(
            response.status_code,
            302,
            response.content.decode()[:4000],
        )
        self.assertFalse(
            EveFitting.objects.filter(name="[TEST] New Fit").exists()
        )
        draft = EveFitting.all_objects.get(name="[TEST] New Fit")
        self.assertIsNotNone(draft.deleted)
        req = EveFittingChangeRequest.objects.get(fitting=draft)
        self.assertEqual("fitting_create", req.change_kind)
        self.assertEqual("[Rifter, [TEST] New Fit]", req.payload["eft_format"])

    def test_delete_queues_fitting_delete(self):
        fitting = EveFitting.objects.create(
            name="[TEST] Delete Me",
            eft_format="[Rifter, [TEST] Delete Me]",
            ship_id=587,
            description="live",
        )
        url = reverse("admin:fittings_evefitting_delete", args=[fitting.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        csrf = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            response.content.decode(),
        ).group(1)
        response = self.client.post(
            url,
            {"csrfmiddlewaretoken": csrf, "post": "yes"},
        )
        self.assertEqual(
            response.status_code,
            302,
            response.content.decode()[:4000],
        )
        fitting.refresh_from_db()
        self.assertIsNone(fitting.deleted)
        req = EveFittingChangeRequest.objects.get(fitting=fitting)
        self.assertEqual("fitting_delete", req.change_kind)


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

    def test_save_syncs_name_from_eft_without_version_bump(self):
        fitting = EveFitting.objects.create(
            name="Legacy display name",
            eft_format="[Retribution, [ADV-5] Retribution]",
            ship_id=608,
            description="",
        )
        # create() already syncs; force a mismatch via update bypassing save().
        EveFitting.objects.filter(pk=fitting.pk).update(
            name="Legacy display name"
        )
        fitting.refresh_from_db()
        version_before = fitting.latest_version
        fitting.save()
        fitting.refresh_from_db()
        self.assertEqual("[ADV-5] Retribution", fitting.name)
        self.assertEqual(version_before, fitting.latest_version)
        self.assertEqual(
            0, EveFittingHistory.objects.filter(fitting=fitting).count()
        )

    def test_create_derives_name_from_eft(self):
        fitting = EveFitting(
            name="ignored",
            eft_format="[Rifter, From EFT]",
            ship_id=587,
            description="",
        )
        fitting.save()
        self.assertEqual("From EFT", fitting.name)

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
        )
        fitting.set_tag_slugs(["nullsec"], write_history=False)
        version_v1 = fitting.latest_version

        fitting.set_tag_slugs(["nanogang", "nullsec"])

        fitting.refresh_from_db()
        self.assertNotEqual(version_v1, fitting.latest_version)

        history = EveFittingHistory.objects.filter(fitting=fitting)
        self.assertEqual(1, history.count())
        row = history.get()
        self.assertEqual(["nullsec"], row.tags)


class FittingsManageSearchTestCase(TestCase):
    """Custom fittings hub: search bar filters the list."""

    def setUp(self):
        super().setUp()
        self.make_superuser()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        EveFitting.objects.create(
            name="[ADV-5] Retribution",
            eft_format="[Retribution, [ADV-5] Retribution]",
            ship_id=608,
            description="pulse laser kite",
            aliases="[FL33T] Retribution",
        )
        EveFitting.objects.create(
            name="[NVY-30] Tornado",
            eft_format="[Tornado, [NVY-30] Tornado]",
            ship_id=12038,
            description="artillery doctrine",
        )

    def test_manage_page_includes_search_form(self):
        url = reverse("admin:fittings_manage_fittings")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('name="q"', html)
        self.assertIn("Search fittings", html)
        self.assertIn("[ADV-5] Retribution", html)
        self.assertIn("[NVY-30] Tornado", html)

    def test_manage_page_filters_by_query(self):
        url = reverse("admin:fittings_manage_fittings")
        response = self.client.get(url, {"q": "Tornado"})
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("[NVY-30] Tornado", html)
        self.assertNotIn("[ADV-5] Retribution", html)
        self.assertIn('value="Tornado"', html)

    def test_manage_page_filters_by_alias(self):
        url = reverse("admin:fittings_manage_fittings")
        response = self.client.get(url, {"q": "FL33T"})
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("[ADV-5] Retribution", html)
        self.assertNotIn("[NVY-30] Tornado", html)


class EveFittingModuleSubstitutionTestCase(TestCase):
    """Per-fitting seeder module fallbacks."""

    def setUp(self):
        super().setUp()
        category, _ = EveCategory.objects.get_or_create(
            id=7,
            defaults={"name": "Module", "published": True},
        )
        group, _ = EveGroup.objects.get_or_create(
            id=55,
            defaults={
                "name": "Propulsion Module",
                "eve_category": category,
                "published": True,
            },
        )
        self.preferred, _ = EveType.objects.get_or_create(
            id=440,
            defaults={
                "name": "5MN Microwarpdrive II",
                "eve_group": group,
                "published": True,
            },
        )
        self.substitute, _ = EveType.objects.get_or_create(
            id=434,
            defaults={
                "name": "5MN Y-T8 Compact Microwarpdrive",
                "eve_group": group,
                "published": True,
            },
        )
        self.fitting = EveFitting.objects.create(
            name="[TEST] Sub Fit",
            eft_format="[Rifter, [TEST] Sub Fit]",
            ship_id=587,
            description="Base",
        )

    def test_str_and_create(self):
        row = EveFittingModuleSubstitution.objects.create(
            fitting=self.fitting,
            preferred_module=self.preferred,
            substitute_module=self.substitute,
            notes="meta fallback",
        )
        self.assertEqual(
            "5MN Microwarpdrive II → 5MN Y-T8 Compact Microwarpdrive",
            str(row),
        )
        self.assertEqual(1, self.fitting.module_substitutions.count())

    def test_clean_rejects_identical_modules(self):
        row = EveFittingModuleSubstitution(
            fitting=self.fitting,
            preferred_module=self.preferred,
            substitute_module=self.preferred,
        )
        with self.assertRaises(Exception) as ctx:
            row.full_clean()
        self.assertIn("substitute_module", ctx.exception.message_dict)

    def test_unique_preferred_per_fitting(self):
        EveFittingModuleSubstitution.objects.create(
            fitting=self.fitting,
            preferred_module=self.preferred,
            substitute_module=self.substitute,
        )
        with self.assertRaises(Exception):
            EveFittingModuleSubstitution.objects.create(
                fitting=self.fitting,
                preferred_module=self.preferred,
                substitute_module=self.substitute,
            )


class EveFittingModuleSubstitutionAdminTestCase(TestCase):
    """Admin inline for module substitutions saves without approval queue."""

    def setUp(self):
        super().setUp()
        self.make_superuser()
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)
        category, _ = EveCategory.objects.get_or_create(
            id=7,
            defaults={"name": "Module", "published": True},
        )
        group, _ = EveGroup.objects.get_or_create(
            id=55,
            defaults={
                "name": "Propulsion Module",
                "eve_category": category,
                "published": True,
            },
        )
        self.preferred, _ = EveType.objects.get_or_create(
            id=440,
            defaults={
                "name": "5MN Microwarpdrive II",
                "eve_group": group,
                "published": True,
            },
        )
        self.substitute, _ = EveType.objects.get_or_create(
            id=434,
            defaults={
                "name": "5MN Y-T8 Compact Microwarpdrive",
                "eve_group": group,
                "published": True,
            },
        )
        # Ensure shared group even if types already existed from other suites.
        EveType.objects.filter(pk__in=[440, 434]).update(eve_group=group)
        self.preferred.refresh_from_db()
        self.substitute.refresh_from_db()
        self.fitting = EveFitting.objects.create(
            name="[TEST] Sub Fit",
            eft_format=("[Rifter, [TEST] Sub Fit]\n" "5MN Microwarpdrive II"),
            ship_id=587,
            description="Base",
        )

    def test_change_page_shows_substitution_inline(self):
        url = reverse(
            "admin:fittings_evefitting_change", args=[self.fitting.pk]
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("Module substitutions", html)
        self.assertIn("If unavailable", html)
        self.assertIn("Buy instead", html)
        self.assertIn("admin-autocomplete", html)
        self.assertIn(f'data-fitting-id="{self.fitting.pk}"', html)
        self.assertIn("module_substitution_autocomplete.js", html)

    def test_change_page_preferred_only_lists_fit_items(self):
        # Autocomplete options come from AJAX; widget must be scoped to fitting.
        url = reverse(
            "admin:fittings_evefitting_change", args=[self.fitting.pk]
        )
        response = self.client.get(url)
        html = response.content.decode()
        self.assertIn(f'data-fitting-id="{self.fitting.pk}"', html)
        self.assertIn('data-field-name="preferred_module"', html)
        self.assertIn('data-field-name="substitute_module"', html)

    def test_save_substitution_via_inline(self):
        url = reverse(
            "admin:fittings_evefitting_change", args=[self.fitting.pk]
        )
        response = self.client.get(url)
        csrf = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            response.content.decode(),
        ).group(1)
        post = {
            "csrfmiddlewaretoken": csrf,
            "eft_format": self.fitting.eft_format,
            "description": self.fitting.description,
            "aliases": "",
            "minimum_pod": "",
            "recommended_pod": "",
            **_empty_fitting_inline_formsets(
                **{
                    "module_substitutions-TOTAL_FORMS": "1",
                    "module_substitutions-0-preferred_module": (
                        self.preferred.pk
                    ),
                    "module_substitutions-0-substitute_module": (
                        self.substitute.pk
                    ),
                    "module_substitutions-0-notes": "buy meta if T2 dry",
                }
            ),
            "_save": "Save",
        }
        response = self.client.post(url, post)
        self.assertEqual(
            response.status_code,
            302,
            response.content.decode()[:4000],
        )
        row = EveFittingModuleSubstitution.objects.get(fitting=self.fitting)
        self.assertEqual(self.preferred.pk, row.preferred_module_id)
        self.assertEqual(self.substitute.pk, row.substitute_module_id)
        self.assertEqual("buy meta if T2 dry", row.notes)
        self.assertFalse(
            EveFittingChangeRequest.objects.filter(
                fitting=self.fitting
            ).exists()
        )
