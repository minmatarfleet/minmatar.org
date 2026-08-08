from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.utils import timezone

from app.test import TestCase
from eveonline.models import EveLocation
from fittings.models import EveDoctrine, EveDoctrineFitting, EveFitting
from fleets.models import (
    EveFleet,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetInstanceMemberShipSnapshot,
)
from market.helpers.contract_fleet_demand import (
    estimate_typical_fleet_size,
    typical_fleet_size_by_fitting,
)
from market.models import EveMarketContract, EveMarketContractExpectation


class EstimateTypicalFleetSizeTestCase(SimpleTestCase):
    def test_drops_small_outlier_fleets(self):
        # Raw median would be 7; dropping 2s (< half of 7) → median 13.
        self.assertEqual(
            estimate_typical_fleet_size([2, 2, 6, 8, 19, 19]),
            13,
        )

    def test_keeps_samples_when_too_few_for_filter(self):
        self.assertEqual(estimate_typical_fleet_size([2, 8]), 5)

    def test_empty(self):
        self.assertIsNone(estimate_typical_fleet_size([]))


@patch("fleets.signals.update_fleet_schedule")
class TypicalFleetSizeTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="fc")
        self.loc = EveLocation.objects.create(
            location_id=5555,
            location_name="Staging",
            solar_system_id=1,
            solar_system_name="Somewhere",
            market_active=True,
        )
        self.fit = EveFitting.objects.create(
            name="[FL33T] Test Battleship",
            ship_id=644,
            description="Test",
            eft_format="[Typhoon, [FL33T] Test Battleship]",
        )
        self.doctrine = EveDoctrine.objects.create(
            name="Test Doctrine",
            type="strategic",
            description="Test",
        )
        EveDoctrineFitting.objects.create(
            doctrine=self.doctrine,
            fitting=self.fit,
            role="primary",
        )
        EveMarketContractExpectation.objects.create(
            fitting=self.fit,
            location=self.loc,
            quantity=20,
        )

    def _add_fleet_with_hulls(
        self, fleet_pk: int, instance_id: int, hulls: int
    ):
        now = timezone.now()
        fleet = EveFleet.objects.create(
            type="strategic",
            start_time=now - timedelta(days=7),
            created_by=self.user,
            doctrine=self.doctrine,
            status="complete",
        )
        instance = EveFleetInstance.objects.create(
            id=instance_id,
            eve_fleet=fleet,
        )
        for i in range(hulls):
            EveFleetInstanceMember.objects.create(
                eve_fleet_instance=instance,
                character_id=1000 + fleet_pk * 100 + i,
                character_name=f"Pilot {i}",
                role="squad_member",
                role_name="Squad Member",
                ship_type_id=self.fit.ship_id,
                ship_name="Typhoon",
                solar_system_id=1,
                solar_system_name="Somewhere",
                squad_id=1,
                wing_id=1,
            )
        return fleet

    def test_median_hull_count_from_doctrine_fleets(self, schedule_mock):
        self._add_fleet_with_hulls(1, instance_id=9001, hulls=4)
        self._add_fleet_with_hulls(2, instance_id=9002, hulls=8)
        self._add_fleet_with_hulls(3, instance_id=9003, hulls=8)

        sizes = typical_fleet_size_by_fitting(
            fitting_ids=[self.fit.id],
            location=self.loc,
            use_burst_fallback=False,
        )
        self.assertEqual(sizes[self.fit.id], 8)

    def test_excludes_small_outlier_fleets(self, schedule_mock):
        self._add_fleet_with_hulls(1, instance_id=9001, hulls=2)
        self._add_fleet_with_hulls(2, instance_id=9002, hulls=2)
        self._add_fleet_with_hulls(3, instance_id=9003, hulls=6)
        self._add_fleet_with_hulls(4, instance_id=9004, hulls=8)
        self._add_fleet_with_hulls(5, instance_id=9005, hulls=19)
        self._add_fleet_with_hulls(6, instance_id=9006, hulls=19)

        sizes = typical_fleet_size_by_fitting(
            fitting_ids=[self.fit.id],
            location=self.loc,
            use_burst_fallback=False,
        )
        self.assertEqual(sizes[self.fit.id], 13)

    def test_uses_peak_concurrent_from_ship_snapshots(self, schedule_mock):
        """End-of-fleet capsules should not erase peak doctrine hull counts."""
        now = timezone.now()
        fleet = EveFleet.objects.create(
            type="strategic",
            start_time=now - timedelta(days=3),
            created_by=self.user,
            doctrine=self.doctrine,
            status="complete",
        )
        instance = EveFleetInstance.objects.create(id=9100, eve_fleet=fleet)
        members = []
        for i in range(5):
            member = EveFleetInstanceMember.objects.create(
                eve_fleet_instance=instance,
                character_id=7000 + i,
                character_name=f"Pilot {i}",
                role="squad_member",
                role_name="Squad Member",
                # Final state: podded.
                ship_type_id=670,
                ship_name="Capsule",
                solar_system_id=1,
                solar_system_name="Somewhere",
                squad_id=1,
                wing_id=1,
            )
            members.append(member)
        for member in members:
            EveFleetInstanceMemberShipSnapshot.objects.create(
                member=member,
                ship_type_id=self.fit.ship_id,
                ship_name="Typhoon",
                solar_system_id=1,
                solar_system_name="Somewhere",
            )
        for member in members:
            EveFleetInstanceMemberShipSnapshot.objects.create(
                member=member,
                ship_type_id=670,
                ship_name="Capsule",
                solar_system_id=1,
                solar_system_name="Somewhere",
            )

        sizes = typical_fleet_size_by_fitting(
            fitting_ids=[self.fit.id],
            location=self.loc,
            use_burst_fallback=False,
        )
        self.assertEqual(sizes[self.fit.id], 5)

    def test_falls_back_to_purchase_bursts(self, schedule_mock):
        now = timezone.now()
        for i, minute in enumerate((0, 10, 20)):
            EveMarketContract.objects.create(
                id=5000 + i,
                location=self.loc,
                fitting=self.fit,
                status="finished",
                price=1.0,
                issuer_external_id=1,
                completed_at=now
                - timedelta(hours=2)
                + timedelta(minutes=minute),
            )
        sizes = typical_fleet_size_by_fitting(
            fitting_ids=[self.fit.id],
            location=self.loc,
            use_burst_fallback=True,
        )
        self.assertEqual(sizes[self.fit.id], 3)
