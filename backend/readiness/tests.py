from datetime import datetime, timedelta

from django.test import Client

from app.test import TestCase

from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember
from fleets.tests import disconnect_fleet_signals, setup_fleet_reference_data

BASE_URL = "/api/readiness"


class ReadinessRouterTestCase(TestCase):
    """Test cases for the Pilot Readiness router."""

    def setUp(self):
        self.client = Client()

        super().setUp()

        disconnect_fleet_signals()
        setup_fleet_reference_data()

        super().make_superuser()

    def add_fleet_member(
        self, instance: EveFleetInstance, char_id: int, squad: int = 1
    ):
        EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=char_id,
            character_name=f"Char {char_id}",
            ship_type_id=1,
            solar_system_id=1,
            squad_id=squad,
            wing_id=1,
            join_time=datetime.now() - timedelta(days=1),
        )

    def test_readiness_summary(self):
        fleet = EveFleet.objects.create(
            description="Test fleet 1",
            type="strategic",
            location_id=123,
            start_time=datetime.now(),
        )
        instance = EveFleetInstance.objects.create(
            id=1234,
            eve_fleet=fleet,
        )
        self.add_fleet_member(instance, 1, 1)
        self.add_fleet_member(instance, 2, 2)
        self.add_fleet_member(instance, 3, 1)

        response = self.client.get(
            f"{BASE_URL}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            response.json(),
            {
                "summary": "Testing",
                "total": 2,
                "values": [
                    {"key": "Test Location, Squad 1", "value": 2},
                    {"key": "Test Location, Squad 2", "value": 1},
                ],
            },
        )
