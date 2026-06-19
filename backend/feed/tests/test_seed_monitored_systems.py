from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase

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

    @patch("feed.management.commands.seed_feed_monitored_systems.requests.get")
    def test_seed_from_esi_resolves_region_via_constellation(
        self, mock_get: MagicMock
    ):
        def fake_get(url, **kwargs):
            response = MagicMock()
            if url.endswith("/fw/systems/"):
                response.status_code = 200
                response.json.return_value = [
                    {"solar_system_id": 30003067},
                    {"solar_system_id": 30002957},
                ]
                return response
            if url.endswith("/universe/systems/30003067/"):
                response.status_code = 200
                response.json.return_value = {
                    "name": "Huola",
                    "constellation_id": 20000448,
                }
                return response
            if url.endswith("/universe/systems/30002957/"):
                response.status_code = 200
                response.json.return_value = {
                    "name": "Other",
                    "constellation_id": 20000001,
                }
                return response
            if url.endswith("/universe/constellations/20000448/"):
                response.status_code = 200
                response.json.return_value = {"region_id": 10000038}
                return response
            if url.endswith("/universe/constellations/20000001/"):
                response.status_code = 200
                response.json.return_value = {"region_id": 99999999}
                return response
            raise AssertionError(f"Unexpected URL: {url}")

        mock_get.side_effect = fake_get

        count = seed_from_esi()

        self.assertEqual(count, 1)
        system = FeedMonitoredSystem.objects.get(solar_system_id=30003067)
        self.assertEqual(system.name, "Huola")
        self.assertTrue(system.is_active)
