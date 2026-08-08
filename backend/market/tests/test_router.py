from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from app.test import TestCase

from eveonline.models import EveCorporation, EveLocation
from fittings.models import EveDoctrine, EveDoctrineFitting, EveFitting
from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
)

BASE_URL = "/api/market"


class MarketRouterTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        cache.clear()
        super().setUp()

    def _setup_expecation(self):
        loc = EveLocation.objects.create(
            location_id=1234,
            location_name="Somewhere else",
            solar_system_id=1,
            solar_system_name="Somewhere",
            market_active=True,
        )
        fit = EveFitting.objects.create(
            name="[NVY-5] Atron",
            ship_id=1,
            description="Testing",
            eft_format="[Atron, [NVY-5] Atron]",
        )
        return EveMarketContractExpectation.objects.create(
            fitting=fit,
            location=loc,
            quantity=10,
        )

    def test_expectations_by_location(self):
        self._setup_expecation()

        response = self.client.get(f"{BASE_URL}/expectations/by-location")
        self.assertEqual(200, response.status_code)
        locations = response.json()
        self.assertEqual(1, len(locations))
        self.assertEqual(1, len(locations[0]["expectations"]))

    def test_get_contracts(self):
        expectation = self._setup_expecation()

        timestamp = timezone.now()

        EveMarketContract.objects.create(
            id=1234,
            location=expectation.location,
            fitting=expectation.fitting,
            status="outstanding",
            price=123.45,
            issuer_external_id=1,
            created_at=timestamp,
        )

        response = self.client.get(
            f"{BASE_URL}/contracts?location_id={expectation.location.location_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual("[NVY-5] Atron", data[0]["title"])
        self.assertEqual(1, data[0]["current_quantity"])
        self.assertEqual(10, data[0]["desired_quantity"])
        self.assertEqual(1, data[0]["ship_id"])
        self.assertEqual(
            expectation.location.location_id, data[0]["location_id"]
        )
        self.assertEqual("thin", data[0]["readiness"])
        self.assertEqual(1, len(data[0]["sellers"]))
        self.assertEqual(1, data[0]["sellers"][0]["character_id"])
        self.assertEqual(1, data[0]["sellers"][0]["quantity"])
        self.assertIsNone(data[0]["sellers"][0]["corporation_id"])
        self.assertIn(
            str(timestamp)[0:19], data[0]["latest_contract_timestamp"]
        )
        self.assertNotIn("responsibilities", data[0])
        self.assertIn("doctrines", data[0])
        self.assertIsInstance(data[0]["doctrines"], list)
        self.assertNotIn("historical_quantity", data[0])
        self.assertNotIn("volume_28d", data[0])
        self.assertNotIn("fleets_remaining", data[0])
        self.assertNotIn("fleets_per_month", data[0])

    def test_get_contracts_metrics_includes_finished_volume_windows(self):
        expectation = self._setup_expecation()
        now = timezone.now()

        EveMarketContract.objects.create(
            id=2001,
            location=expectation.location,
            fitting=expectation.fitting,
            status="finished",
            price=1.0,
            issuer_external_id=1,
            completed_at=now - timedelta(hours=12),
        )
        EveMarketContract.objects.create(
            id=2002,
            location=expectation.location,
            fitting=expectation.fitting,
            status="finished",
            price=1.0,
            issuer_external_id=1,
            completed_at=now - timedelta(days=6),
        )
        EveMarketContract.objects.create(
            id=2003,
            location=expectation.location,
            fitting=expectation.fitting,
            status="finished",
            price=1.0,
            issuer_external_id=1,
            completed_at=now - timedelta(days=20),
        )
        EveMarketContract.objects.create(
            id=2004,
            location=expectation.location,
            fitting=expectation.fitting,
            status="finished",
            price=1.0,
            issuer_external_id=1,
            completed_at=now - timedelta(days=60),
        )

        response = self.client.get(
            f"{BASE_URL}/contracts/metrics?location_id={expectation.location.location_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual(expectation.fitting.id, data[0]["fitting_id"])
        self.assertEqual(3, data[0]["volume_28d"])

    def test_get_contracts_collapses_corp_listings_to_corporation(self):
        """Character listings for the same corp show as one corporation seller."""
        expectation = self._setup_expecation()
        EveCorporation.objects.create(
            corporation_id=98000001,
            name="Minmatar Fleet Corp",
        )
        for contract_id in (5001, 5002, 5003):
            EveMarketContract.objects.create(
                id=contract_id,
                location=expectation.location,
                fitting=expectation.fitting,
                status="outstanding",
                price=1.0,
                issuer_external_id=42,
                issuer_corporation_id=98000001,
            )
        # Personal listing from the same character stays separate.
        EveMarketContract.objects.create(
            id=5004,
            location=expectation.location,
            fitting=expectation.fitting,
            status="outstanding",
            price=1.0,
            issuer_external_id=42,
            issuer_corporation_id=None,
        )

        response = self.client.get(
            f"{BASE_URL}/contracts?location_id={expectation.location.location_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        sellers = data[0]["sellers"]
        self.assertEqual(2, len(sellers))
        corp_seller = next(
            s for s in sellers if s["corporation_id"] == 98000001
        )
        char_seller = next(s for s in sellers if s["character_id"] == 42)
        self.assertEqual(3, corp_seller["quantity"])
        self.assertEqual(
            "Minmatar Fleet Corp", corp_seller["corporation_name"]
        )
        self.assertIsNone(corp_seller["character_id"])
        self.assertEqual(1, char_seller["quantity"])
        self.assertIsNone(char_seller["corporation_id"])

    @patch("fleets.signals.update_fleet_schedule")
    def test_get_contracts_metrics_includes_fleets_remaining_from_fleet_comps(
        self, schedule_mock
    ):
        del schedule_mock
        expectation = self._setup_expecation()
        now = timezone.now()
        user = User.objects.create(username="ops-fc")
        doctrine = EveDoctrine.objects.create(
            name="Ops Doctrine",
            type="strategic",
            description="Ops",
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine,
            fitting=expectation.fitting,
            role="primary",
        )
        # Two fleets with 3 of this hull → typical size 3.
        for instance_id, hulls in ((9101, 3), (9102, 3)):
            fleet = EveFleet.objects.create(
                type="strategic",
                start_time=now - timedelta(days=3),
                created_by=user,
                doctrine=doctrine,
                status="complete",
            )
            instance = EveFleetInstance.objects.create(
                id=instance_id,
                eve_fleet=fleet,
            )
            for i in range(hulls):
                EveFleetInstanceMember.objects.create(
                    eve_fleet_instance=instance,
                    character_id=2000 + instance_id + i,
                    character_name=f"Pilot {i}",
                    role="squad_member",
                    role_name="Squad Member",
                    ship_type_id=expectation.fitting.ship_id,
                    ship_name="Ship",
                    solar_system_id=1,
                    solar_system_name="Somewhere",
                    squad_id=1,
                    wing_id=1,
                )
        # Outstanding stock: 5 → ceil(5/3) = 2 fleets remaining.
        for i in range(5):
            EveMarketContract.objects.create(
                id=4000 + i,
                location=expectation.location,
                fitting=expectation.fitting,
                status="outstanding",
                price=1.0,
                issuer_external_id=1,
                created_at=now,
            )

        response = self.client.get(
            f"{BASE_URL}/contracts/metrics?location_id={expectation.location.location_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual(expectation.fitting.id, data[0]["fitting_id"])
        self.assertEqual(3, data[0]["typical_fleet_size"])
        self.assertEqual(2, data[0]["fleets_remaining"])
        # 2 fleets with this hull in 90d lookback → 2 * 30/90 = 0.7 /mo
        self.assertEqual(0.7, data[0]["fleets_per_month"])

    def test_get_contracts_includes_ready_and_understocked(self):
        """All fittings are returned, including at-target (ready) stock."""
        loc = EveLocation.objects.create(
            location_id=7777,
            location_name="Mixed stock location",
            solar_system_id=1,
            solar_system_name="Somewhere",
            market_active=True,
        )
        ready_fit = EveFitting.objects.create(
            name="[NVY-5] Ready Fit",
            ship_id=608,
            description="At target",
            eft_format="[Atron, [NVY-5] Ready Fit]",
        )
        thin_fit = EveFitting.objects.create(
            name="[NVY-5] Thin Fit",
            ship_id=587,
            description="Under target",
            eft_format="[Rifter, [NVY-5] Thin Fit]",
        )
        EveMarketContractExpectation.objects.create(
            fitting=ready_fit,
            location=loc,
            quantity=2,
        )
        EveMarketContractExpectation.objects.create(
            fitting=thin_fit,
            location=loc,
            quantity=5,
        )
        for i in range(2):
            EveMarketContract.objects.create(
                id=7000 + i,
                location=loc,
                fitting=ready_fit,
                status="outstanding",
                price=1.0,
                issuer_external_id=1,
            )
        EveMarketContract.objects.create(
            id=7100,
            location=loc,
            fitting=thin_fit,
            status="outstanding",
            price=1.0,
            issuer_external_id=1,
        )

        response = self.client.get(
            f"{BASE_URL}/contracts?location_id={loc.location_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(
            2,
            len(data),
            msg=f"expected 2 fittings, got {data!r}",
        )
        by_title = {row["title"]: row for row in data}
        self.assertEqual("ready", by_title["[NVY-5] Ready Fit"]["readiness"])
        self.assertEqual(2, by_title["[NVY-5] Ready Fit"]["current_quantity"])
        self.assertEqual("thin", by_title["[NVY-5] Thin Fit"]["readiness"])
        self.assertEqual(1, by_title["[NVY-5] Thin Fit"]["current_quantity"])
        self.assertEqual(608, by_title["[NVY-5] Ready Fit"]["ship_id"])
        self.assertEqual(1, len(by_title["[NVY-5] Ready Fit"]["sellers"]))
        self.assertEqual(
            2, by_title["[NVY-5] Ready Fit"]["sellers"][0]["quantity"]
        )
        # Higher fill first (100% -> 0%), then no-expectation
        readiness_order = [row["readiness"] for row in data]
        self.assertIn("thin", readiness_order)
        self.assertIn("ready", readiness_order)
        self.assertLess(
            readiness_order.index("ready"), readiness_order.index("thin")
        )

    def test_get_contracts_unknown_location_returns_empty(self):
        response = self.client.get(
            f"{BASE_URL}/contracts?location_id=999999",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json())

    def test_get_contracts_includes_fittings_with_contracts_but_no_expectation(
        self,
    ):
        """Fittings that have contracts at the location but no expectation are still returned."""
        loc = EveLocation.objects.create(
            location_id=5555,
            location_name="Contract-only location",
            solar_system_id=1,
            solar_system_name="Somewhere",
            market_active=True,
        )
        fit = EveFitting.objects.create(
            name="[NVY-9] No Expectation",
            ship_id=2,
            description="No expectation",
            eft_format="[Merlin, [NVY-9] No Expectation]",
        )
        EveMarketContract.objects.create(
            id=9999,
            location=loc,
            fitting=fit,
            status="outstanding",
            price=1.0,
            issuer_external_id=1,
        )
        response = self.client.get(
            f"{BASE_URL}/contracts?location_id={loc.location_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual("[NVY-9] No Expectation", data[0]["title"])
        self.assertEqual(1, data[0]["current_quantity"])
        self.assertEqual(0, data[0]["desired_quantity"])
        self.assertIsNone(data[0]["expectation_id"])
        self.assertEqual(2, data[0]["ship_id"])
        self.assertEqual(loc.location_id, data[0]["location_id"])
        self.assertEqual("unknown", data[0]["readiness"])
        self.assertNotIn("responsibilities", data[0])
        self.assertEqual([], data[0]["doctrines"])

    def test_inactive_market(self):
        # Test that locations with market_active=False are not included
        # in market-related queries. This test verifies the location model
        # behavior rather than testing a removed endpoint.
        location_inactive = EveLocation.objects.create(
            location_id=1,
            location_name="Location 1",
            solar_system_id=1,
            solar_system_name="Solar 1",
            short_name="One",
            market_active=False,
        )
        location_active = EveLocation.objects.create(
            location_id=2,
            location_name="Location 2",
            solar_system_id=2,
            solar_system_name="Solar 2",
            short_name="Two",
            market_active=True,
        )

        self.assertFalse(location_inactive.market_active)
        self.assertTrue(location_active.market_active)

        active_locations = EveLocation.objects.filter(market_active=True)
        self.assertEqual(1, active_locations.count())
        self.assertEqual("Location 2", active_locations.first().location_name)
