import json
from django.test import Client
from django.contrib.auth.models import Permission
from django.utils import timezone

from app.test import TestCase
from structures.models import EveStructureTimer


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

    def test_create_structure_timer_without_permission_is_403(self):
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

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Permission denied")

    def test_verify_structure_timer_without_permission_is_403(self):
        timer = EveStructureTimer.objects.create(
            state="anchoring",
            type="fortizar",
            timer=timezone.now(),
            created_by=self.user,
            corporation_name="Test",
            system_name="Sosala",
            name="WATERMELLON",
        )

        response = self.client.post(
            f"/api/structures/timers/{timer.id}/verify",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
            content_type="application/json",
            data=json.dumps(
                {"corporation_name": "Other", "alliance_name": "Other"}
            ),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Permission denied")
        timer.refresh_from_db()
        self.assertEqual(timer.corporation_name, "Test")
