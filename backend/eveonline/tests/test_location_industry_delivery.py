"""EveLocation.industry_delivery and dock_access."""

import importlib

from django.apps import apps
from django.test import TestCase

from eveonline.models import EveLocation

migration = importlib.import_module(
    "eveonline.migrations.0117_eve_location_industry_delivery"
)


def _location(location_id, **fields):
    defaults = {
        "location_name": f"Location {location_id}",
        "solar_system_id": 30000142,
        "solar_system_name": "Jita",
        "short_name": f"L{location_id}",
    }
    defaults.update(fields)
    return EveLocation.objects.create(location_id=location_id, **defaults)


class IndustryDeliveryFieldTestCase(TestCase):
    def test_defaults_off_and_open_docking(self):
        location = _location(1)
        location.refresh_from_db()
        self.assertFalse(location.industry_delivery)
        self.assertEqual([], location.dock_access)

    def test_soft_delete_clears_industry_delivery(self):
        location = _location(2, industry_delivery=True)
        location.delete()
        stored = EveLocation.all_objects.get(pk=2)
        self.assertFalse(stored.industry_delivery)


class IndustryDeliveryMigrationTestCase(TestCase):
    def test_forward_turns_it_on_for_the_staging_only(self):
        staging = _location(10, staging_active=True)
        other = _location(11)
        migration.staging_delivers(apps, None)
        staging.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(staging.industry_delivery)
        self.assertFalse(other.industry_delivery)

    def test_reverse_turns_it_off(self):
        location = _location(12, industry_delivery=True)
        migration.no_delivery(apps, None)
        location.refresh_from_db()
        self.assertFalse(location.industry_delivery)
