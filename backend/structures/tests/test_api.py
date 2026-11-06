import json
from django.test import Client
from django.contrib.auth.models import Permission
from django.utils import timezone

from app.test import TestCase
from audit.models import AuditEntry
from structures.models import EveStructurePing, EveStructureTimer


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


class StructureTimerCorrectionTests(TestCase):
    """Edit and delete wrong timers; read the ping log."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.timer = EveStructureTimer.objects.create(
            name="WATERMELLON",
            state="armor",
            type="fortizar",
            timer=timezone.now() + timezone.timedelta(days=1),
            system_name="Sosala",
            corporation_name="Wrong Corp",
        )
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def grant(self):
        self.user.user_permissions.add(
            Permission.objects.get(
                codename="change_evestructuretimer",
                content_type__app_label="structures",
            )
        )

    def patch(self, data):
        return self.client.patch(
            f"/api/structures/timers/{self.timer.id}",
            data=json.dumps(data),
            content_type="application/json",
            **self.headers,
        )

    def test_everything_needs_the_feature(self):
        self.assertEqual(403, self.patch({"name": "x"}).status_code)
        deleted = self.client.delete(
            f"/api/structures/timers/{self.timer.id}", **self.headers
        )
        self.assertEqual(403, deleted.status_code)
        pings = self.client.get("/api/structures/pings", **self.headers)
        self.assertEqual(403, pings.status_code)
        self.assertTrue(
            EveStructureTimer.objects.filter(id=self.timer.id).exists()
        )

    def test_edit_changes_fields_and_is_audited(self):
        self.grant()
        response = self.patch(
            {"corporation_name": "Right Corp", "state": "hull"}
        )
        self.assertEqual(200, response.status_code)
        self.timer.refresh_from_db()
        self.assertEqual("Right Corp", self.timer.corporation_name)
        self.assertEqual("hull", self.timer.state)
        self.assertEqual(self.user, self.timer.updated_by)
        entry = AuditEntry.objects.get()
        self.assertEqual(self.user, entry.user)
        self.assertIn("Right Corp", entry.summary)

    def test_edit_with_no_changes_writes_no_audit(self):
        self.grant()
        self.assertEqual(200, self.patch({"name": "WATERMELLON"}).status_code)
        self.assertFalse(AuditEntry.objects.exists())

    def test_edit_rejects_blank_name_and_unknown_timer(self):
        self.grant()
        self.assertEqual(400, self.patch({"name": "  "}).status_code)
        missing = self.client.patch(
            "/api/structures/timers/9999",
            data=json.dumps({"name": "x"}),
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(404, missing.status_code)

    def test_delete_removes_the_timer_and_is_audited(self):
        self.grant()
        response = self.client.delete(
            f"/api/structures/timers/{self.timer.id}", **self.headers
        )
        self.assertEqual(204, response.status_code)
        self.assertFalse(EveStructureTimer.objects.exists())
        self.assertIn("Deleted timer", AuditEntry.objects.get().summary)

    def test_pings_can_be_filtered_to_failures(self):
        self.grant()
        EveStructurePing.objects.create(
            notification_id=1,
            notification_type="StructureUnderAttack",
            summary="ok",
            discord_success=True,
        )
        EveStructurePing.objects.create(
            notification_id=2,
            notification_type="StructureUnderAttack",
            summary="bad",
            discord_success=False,
        )
        both = self.client.get("/api/structures/pings", **self.headers)
        self.assertEqual(2, len(both.json()))
        failed = self.client.get(
            "/api/structures/pings?failed_only=true", **self.headers
        )
        self.assertEqual(["bad"], [p["summary"] for p in failed.json()])
