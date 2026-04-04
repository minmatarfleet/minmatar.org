"""Soft delete behavior for EveLocation, EveFitting, and EveStructure."""

from django.test import TestCase

from eveonline.models import EveCorporation, EveLocation
from fittings.models import EveFitting
from structures.models import EveStructure


class EveLocationSoftDeleteTestCase(TestCase):
    def test_soft_delete_hides_from_default_manager(self):
        loc = EveLocation.objects.create(
            location_id=100,
            location_name="Test Loc",
            solar_system_id=1,
            solar_system_name="Sys",
            short_name="t",
            market_active=True,
            prices_active=True,
            price_baseline=True,
            freight_active=True,
            staging_active=True,
        )
        loc.delete()
        self.assertEqual(0, EveLocation.objects.count())
        self.assertEqual(1, EveLocation.all_objects.count())
        loc_all = EveLocation.all_objects.get(pk=100)
        self.assertIsNotNone(loc_all.deleted)
        self.assertFalse(loc_all.price_baseline)
        self.assertFalse(loc_all.market_active)

    def test_name_reuse_after_soft_delete(self):
        EveFitting.objects.create(
            name="Dup Fit",
            ship_id=587,
            description="d",
            eft_format="[Rifter, Dup Fit]\n\n",
        )
        fit = EveFitting.objects.get(name="Dup Fit")
        fit.delete()
        self.assertEqual(0, EveFitting.objects.filter(name="Dup Fit").count())
        EveFitting.objects.create(
            name="Dup Fit",
            ship_id=587,
            description="d2",
            eft_format="[Rifter, Dup Fit]\n\n",
        )
        self.assertEqual(1, EveFitting.objects.filter(name="Dup Fit").count())


class EveStructureSoftDeleteTestCase(TestCase):
    def test_soft_delete_clears_staging_flag(self):
        corp = EveCorporation.objects.create(corporation_id=999001, name="C")
        st = EveStructure.objects.create(
            id=5001,
            system_id=1,
            system_name="S",
            type_id=1,
            type_name="Fortizar",
            name="Struct",
            reinforce_hour=0,
            corporation=corp,
            is_valid_staging=True,
        )
        st.delete()
        st_refresh = EveStructure.all_objects.get(pk=5001)
        self.assertIsNotNone(st_refresh.deleted)
        self.assertFalse(st_refresh.is_valid_staging)
