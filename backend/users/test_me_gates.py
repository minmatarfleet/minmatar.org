"""GET /api/users/me/gates."""

from django.contrib.auth.models import Permission, User
from django.test import Client, override_settings

from app.test import TestCase
from groups.features.registry import FEATURE_DEFINITIONS
from groups.helpers.feature_access import clear_feature_cache
from groups.management.commands.sync_pilot_features import (
    Command as SyncCommand,
)
from users.helpers import get_user_permissions

URL = "/api/users/me/gates"


class MeGatesTestCase(TestCase):
    def setUp(self):
        super().setUp()
        clear_feature_cache()
        SyncCommand().handle()
        clear_feature_cache()
        self.client = Client()

    def tearDown(self):
        clear_feature_cache()

    def _get(self):
        return self.client.get(URL, HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_requires_auth(self):
        self.assertEqual(self.client.get(URL).status_code, 401)

    def test_returns_features_and_legacy_permissions(self):
        self.user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="fleets", codename="view_evefleet"
            )
        )
        response = self._get()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("fleets.view", body["features"])
        self.assertEqual(
            body["legacy"],
            {
                "permissions": sorted(get_user_permissions(self.user.id)),
                "is_superuser": False,
            },
        )
        self.assertIn("fleets.view_evefleet", body["legacy"]["permissions"])
        self.assertEqual(body["gate_source"], "legacy")

    def test_superuser_gets_every_feature(self):
        self.make_superuser()
        body = self._get().json()
        self.assertEqual(body["features"], sorted(FEATURE_DEFINITIONS))
        self.assertTrue(body["legacy"]["is_superuser"])

    def test_gate_source_follows_setting(self):
        for value in ("shadow", "features"):
            with override_settings(FRONTEND_GATE_SOURCE=value):
                self.assertEqual(self._get().json()["gate_source"], value)
        with override_settings(FRONTEND_GATE_SOURCE="typo"):
            self.assertEqual(self._get().json()["gate_source"], "legacy")

    def test_deleted_user_is_unauthorised(self):
        User.objects.filter(pk=self.user.pk).delete()
        self.assertEqual(self._get().status_code, 401)
