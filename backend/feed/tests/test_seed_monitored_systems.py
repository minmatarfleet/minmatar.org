from __future__ import annotations

from django.test import TestCase

from eveonline.tests.fake_esi_http import FakeEsi, make_response

from feed.management.commands.seed_feed_monitored_systems import (
    seed_from_esi,
    seed_from_fixture,
)
from feed.models import FeedMonitoredSystem


class SeedMonitoredSystemsTestCase(TestCase):
    def test_seed_from_fixture_creates_active_systems(self):
        count = seed_from_fixture()
        self.assertGreater(count, 0)
        self.assertGreater(
            FeedMonitoredSystem.objects.filter(is_active=True).count(), 0
        )

    def test_seed_from_esi_resolves_region_via_constellation(self):
        fake = FakeEsi().install(self)
        fake.add(
            "GET",
            "/fw/systems/",
            make_response(
                200,
                [{"solar_system_id": 30003067}, {"solar_system_id": 30002957}],
            ),
        )
        fake.add(
            "GET",
            "/universe/systems/30003067/",
            make_response(
                200, {"name": "Huola", "constellation_id": 20000448}
            ),
        )
        fake.add(
            "GET",
            "/universe/systems/30002957/",
            make_response(
                200, {"name": "Other", "constellation_id": 20000001}
            ),
        )
        fake.add(
            "GET",
            "/universe/constellations/20000448/",
            make_response(200, {"region_id": 10000038}),
        )
        fake.add(
            "GET",
            "/universe/constellations/20000001/",
            make_response(200, {"region_id": 99999999}),
        )

        count = seed_from_esi()

        self.assertEqual(count, 1)
        system = FeedMonitoredSystem.objects.get(solar_system_id=30003067)
        self.assertEqual(system.name, "Huola")
        self.assertTrue(system.is_active)
