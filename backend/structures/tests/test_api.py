import json
import factory
from django.test import Client
from django.contrib.auth.models import Permission
from django.db.models import signals

from app.test import TestCase

from eveonline.models import EveCharacter, EveCorporation
from structures.models import EveStructureManager


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

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_add_structure_manager(self):
        self.make_superuser()

        char = EveCharacter.objects.create(
            character_id=100001,
            character_name="Test Pilot",
            corporation=EveCorporation.objects.create(
                corporation_id=200001,
                name="Megacorp",
            ),
        )
        char.corporation.ceo = char
        char.corporation.save()

        payload = {
            "character_id": char.character_id,
            "poll_time": 0,
        }

        response = self.client.post(
            "/api/structures/managers",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
            content_type="application/json",
            data=json.dumps(payload),
        )

        self.assertEqual(response.status_code, 200)

        self.assertIsNotNone(
            EveStructureManager.objects.filter(
                character__character_id=char.character_id
            ).first()
        )

        response = self.client.get(
            f"/api/structures/managers?corp_id={char.corporation.corporation_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        managers = response.json()
        self.assertEqual(1, len(managers))
