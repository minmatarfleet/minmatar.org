from datetime import datetime, timedelta

from django.test import Client

from app.test import TestCase

from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember
from fleets.tests import disconnect_fleet_signals

BASE_URL = "/api/readiness"


class ReadinessRouterTestCase(TestCase):
    """Test cases for the Pilot Readiness router."""

    def setUp(self):
        self.client = Client()

        disconnect_fleet_signals()

        super().setUp()

    def add_fleet_member(self, instance: EveFleetInstance, char_id: int):
        EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=char_id,
            character_name=f"Char {char_id}",
            ship_type_id=1,
            solar_system_id=1,
            squad_id=1,
            wing_id=1,
            join_time=datetime.now() - timedelta(days=1),
        )

    def test_readiness_summary(self):
        fleet = EveFleet.objects.create(
            description="Test fleet 1",
            type="strategic",
            start_time=datetime.now(),
        )
        instance = EveFleetInstance.objects.create(
            id=1234,
            eve_fleet=fleet,
        )
        self.add_fleet_member(instance, 1)
        self.add_fleet_member(instance, 2)

        response = self.client.get(
            f"{BASE_URL}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(2, response.json()["total"])
