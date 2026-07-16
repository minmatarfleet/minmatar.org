"""Tests for fitting module substitution helper filtering."""

from django.urls import reverse
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase
from fittings.helpers.module_substitutions import (
    fitting_item_names,
    fitting_item_types,
    types_are_variants,
    variant_types_for,
)
from fittings.models import EveFitting


def _make_type(type_id: int, name: str, group: EveGroup) -> EveType:
    eve_type, _ = EveType.objects.update_or_create(
        id=type_id,
        defaults={
            "name": name,
            "eve_group": group,
            "published": True,
        },
    )
    return eve_type


class ModuleSubstitutionHelpersTestCase(TestCase):
    def setUp(self):
        super().setUp()
        category, _ = EveCategory.objects.get_or_create(
            id=7,
            defaults={"name": "Module", "published": True},
        )
        self.propulsion, _ = EveGroup.objects.get_or_create(
            id=46,
            defaults={
                "name": "Propulsion Module",
                "eve_category": category,
                "published": True,
            },
        )
        self.mwd_t2 = _make_type(440, "5MN Microwarpdrive II", self.propulsion)
        self.mwd_meta = _make_type(
            5973, "5MN Y-T8 Compact Microwarpdrive", self.propulsion
        )
        self.mwd_50 = _make_type(
            12076, "50MN Microwarpdrive II", self.propulsion
        )
        self.ab_t2 = _make_type(438, "5MN Afterburner II", self.propulsion)

    def test_fitting_item_names_excludes_hull(self):
        eft = (
            "[Rifter, [TEST] Fit]\n"
            "5MN Microwarpdrive II\n"
            "5MN Microwarpdrive II\n"
            "Nanite Repair Paste x50\n"
        )
        self.assertEqual(
            ["5MN Microwarpdrive II", "Nanite Repair Paste"],
            fitting_item_names(eft),
        )

    def test_fitting_item_types_resolves_eft_modules(self):
        fitting = EveFitting.objects.create(
            name="[TEST] Fit",
            eft_format="[Rifter, [TEST] Fit]\n5MN Microwarpdrive II\n",
            ship_id=587,
            description="",
        )
        names = list(
            fitting_item_types(fitting).values_list("name", flat=True)
        )
        self.assertEqual(["5MN Microwarpdrive II"], names)

    def test_variants_same_size_family_only(self):
        self.assertTrue(types_are_variants(self.mwd_t2, self.mwd_meta))
        self.assertFalse(types_are_variants(self.mwd_t2, self.mwd_50))
        self.assertFalse(types_are_variants(self.mwd_t2, self.ab_t2))
        variant_names = set(
            variant_types_for(self.mwd_t2).values_list("name", flat=True)
        )
        self.assertIn("5MN Y-T8 Compact Microwarpdrive", variant_names)
        self.assertNotIn("50MN Microwarpdrive II", variant_names)
        self.assertNotIn("5MN Afterburner II", variant_names)


class ModuleSubstitutionAutocompleteViewTestCase(TestCase):
    """Admin autocomplete AJAX is scoped to the fitting / preferred module."""

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
            id=46,
            defaults={
                "name": "Propulsion Module",
                "eve_category": category,
                "published": True,
            },
        )
        self.mwd_t2 = _make_type(440, "5MN Microwarpdrive II", group)
        self.mwd_meta = _make_type(
            5973, "5MN Y-T8 Compact Microwarpdrive", group
        )
        self.mwd_50 = _make_type(12076, "50MN Microwarpdrive II", group)
        self.fitting = EveFitting.objects.create(
            name="[TEST] Fit",
            eft_format="[Rifter, [TEST] Fit]\n5MN Microwarpdrive II",
            ship_id=587,
            description="",
        )
        self.autocomplete_url = reverse("admin:autocomplete")

    def _autocomplete(self, field_name, **extra):
        params = {
            "app_label": "fittings",
            "model_name": "evefittingmodulesubstitution",
            "field_name": field_name,
            "term": "Microwarpdrive",
            **extra,
        }
        return self.client.get(self.autocomplete_url, params)

    def test_preferred_autocomplete_only_fit_items(self):
        response = self._autocomplete(
            "preferred_module",
            fitting_id=str(self.fitting.pk),
        )
        self.assertEqual(200, response.status_code)
        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(str(self.mwd_t2.pk), ids)
        self.assertNotIn(str(self.mwd_meta.pk), ids)
        self.assertNotIn(str(self.mwd_50.pk), ids)

    def test_substitute_autocomplete_only_preferred_variants(self):
        response = self._autocomplete(
            "substitute_module",
            fitting_id=str(self.fitting.pk),
            preferred_id=str(self.mwd_t2.pk),
        )
        self.assertEqual(200, response.status_code)
        ids = {row["id"] for row in response.json()["results"]}
        self.assertIn(str(self.mwd_meta.pk), ids)
        self.assertNotIn(str(self.mwd_t2.pk), ids)
        self.assertNotIn(str(self.mwd_50.pk), ids)
