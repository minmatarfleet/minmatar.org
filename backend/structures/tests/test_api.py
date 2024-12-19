import json
from django.test import Client
from django.contrib.auth.models import Permission

from app.test import TestCase


class StructureTimertests(TestCase):
    """API tests for structure timers API"""

    def setUp(self):
        # create test client
        self.client = Client()

        super().setUp()

    def test_create_structure_timer_original(self):
        permission = Permission.objects.get(codename="add_evestructuretimer")
        self.user.user_permissions.add(permission)

        payload = {
            "selected_item_window": "Sosala - WATERMELLON 0 m Reinforced until 2024.06.23 23:20:58",
            "corporation_name": "Test",
            "state": "anchoring",
            "type": "fortizar",
        }

        response = self.client.post(
            "/api/structures/timers",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
            content_type="application/json",
            data=json.dumps(payload),
        )

        self.assertEqual(response.status_code, 200)

    def test_create_structure_timer_skyhook(self):
        permission = Permission.objects.get(codename="add_evestructuretimer")
        self.user.user_permissions.add(permission)

        payload = {
            "selected_item_window": "Orbital Skyhook (I-MGAB VI) [RED Infrastructure inc] 100 km Reinforced until 2024.12.20 21:27:27",
            "corporation_name": "Test",
            "state": "anchoring",
            "type": "fortizar",
        }

        response = self.client.post(
            "/api/structures/timers",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
            content_type="application/json",
            data=json.dumps(payload),
        )

        self.assertEqual(response.status_code, 200)

    def test_create_structure_timer_structured(self):
        permission = Permission.objects.get(codename="add_evestructuretimer")
        self.user.user_permissions.add(permission)

        payload = {
            "structure_name": "Testing",
            "location": "Sosala",
            "timer": "2024-12-20T21:27:27",
            "corporation_name": "Test",
            "state": "anchoring",
            "type": "fortizar",
            "selected_item_window": "",
        }

        response = self.client.post(
            "/api/structures/timers",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
            content_type="application/json",
            data=json.dumps(payload),
        )

        self.assertEqual(response.status_code, 200)
