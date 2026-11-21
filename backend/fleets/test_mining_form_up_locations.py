import importlib

from django.apps import apps as django_apps
from django.test import TestCase

from buyback.models import EveBuybackSettings
from eveonline.models import EveLocation

migration = importlib.import_module(
    "fleets.migrations.0064_mining_form_up_locations"
)

HYDRA_ID = migration.HYDRA_FREEPORT["location_id"]


def _location(location_id, name, system, **extra):
    return EveLocation.objects.create(
        location_id=location_id,
        location_name=name,
        solar_system_id=30002788,
        solar_system_name=system,
        short_name=name[:32],
        **extra,
    )


class MiningFormUpLocationsTestCase(TestCase):
    def test_turns_on_amo_buyback_athanor_and_gukarla(self):
        amo = _location(1044444444444, "Amo - Athanor Reprocessing", "Amo")
        EveBuybackSettings.objects.create(pk=1, location=amo)

        ids = migration.enable_form_up_locations(django_apps)

        self.assertCountEqual(ids, [HYDRA_ID, amo.location_id])
        self.assertEqual(
            set(
                EveLocation.objects.filter(fleets_active=True).values_list(
                    "location_id", flat=True
                )
            ),
            {HYDRA_ID, amo.location_id},
        )
        hydra = EveLocation.objects.get(location_id=HYDRA_ID)
        self.assertEqual(hydra.solar_system_name, "Gukarla")

    def test_reuses_an_existing_gukarla_row(self):
        _location(HYDRA_ID, "Gukarla - Hydra Freeport", "Gukarla")

        migration.enable_form_up_locations(django_apps)

        self.assertEqual(
            EveLocation.objects.filter(location_id=HYDRA_ID).count(), 1
        )
        self.assertTrue(
            EveLocation.objects.get(location_id=HYDRA_ID).fleets_active
        )

    def test_skips_a_buyback_location_outside_amo(self):
        elsewhere = _location(1044444444445, "Auner - Somewhere", "Auner")
        EveBuybackSettings.objects.create(pk=1, location=elsewhere)

        ids = migration.enable_form_up_locations(django_apps)

        self.assertEqual(ids, [HYDRA_ID])
        elsewhere.refresh_from_db()
        self.assertFalse(elsewhere.fleets_active)

    def test_no_buyback_settings_still_adds_gukarla(self):
        self.assertEqual(
            migration.enable_form_up_locations(django_apps), [HYDRA_ID]
        )
        self.assertTrue(
            EveLocation.objects.get(location_id=HYDRA_ID).fleets_active
        )

    def test_is_idempotent(self):
        migration.enable_form_up_locations(django_apps)
        migration.enable_form_up_locations(django_apps)
        self.assertEqual(
            EveLocation.objects.filter(location_id=HYDRA_ID).count(), 1
        )
