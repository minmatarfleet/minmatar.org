"""Buyback Settings editor: permissions, writes, audit."""

from django.contrib.auth.models import Permission, User
from django.test import Client

from app.test import TestCase
from app.testing import auth_headers
from audit.models import AuditEntry
from buyback.tests.helpers import ensure_type
from buyback.models import BuybackAcceptedItem, EveBuybackSettings
from eveonline.models import EveLocation

BASE = "/api/buyback/manage"


class BuybackManageTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.manager = User.objects.create(username="bb_manager")
        self.manager.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="buyback",
                codename="change_evebuybacksettings",
            )
        )
        self.location = EveLocation.objects.create(
            location_id=42,
            location_name="Buyback Hub",
            short_name="BBH",
            solar_system_id=1,
            solar_system_name="Somewhere",
        )
        self.veldspar = ensure_type(
            type_id=1230,
            name="Veldspar",
            group_id=450,
            group_name="Veldspar",
            category_id=25,
            category_name="Asteroid",
        )

    def _call(self, method, path, user, data=None):
        return getattr(self.client, method)(
            f"{BASE}{path}",
            data=data,
            content_type="application/json",
            **auth_headers(user),
        )

    def test_plain_pilot_is_refused(self):
        for method, path, body in (
            ("get", "/settings", {}),
            ("patch", "/settings", {}),
            ("post", "/items", {"type_id": 1, "category": "ore"}),
            ("patch", "/items/1230", {}),
            ("delete", "/items/1230", {}),
            ("get", "/types?q=ve", {}),
        ):
            with self.subTest(method=method, path=path):
                response = self._call(method, path, self.user, body)
                self.assertEqual(response.status_code, 403)
        self.assertEqual(AuditEntry.objects.count(), 0)

    def test_rates_and_location_are_saved_and_logged(self):
        response = self._call(
            "patch",
            "/settings",
            self.manager,
            {"demand_jita_buy": 0.95, "location_id": 42},
        )
        self.assertEqual(response.status_code, 200)
        settings = EveBuybackSettings.load()
        self.assertEqual(settings.demand_jita_buy, 0.95)
        self.assertEqual(settings.location_id, 42)
        # The stored rate rules follow the editable rates.
        self.assertEqual(settings.rate_rules["demand_jita_buy"], 0.95)
        entry = AuditEntry.objects.get()
        self.assertEqual(entry.user, self.manager)

    def test_rate_outside_range_is_rejected(self):
        response = self._call(
            "patch", "/settings", self.manager, {"ore_refine": 1.5}
        )
        self.assertEqual(response.status_code, 422)

    def test_accepted_item_lifecycle(self):
        added = self._call(
            "post",
            "/items",
            self.manager,
            {"type_id": 1230, "category": "ore"},
        )
        self.assertEqual(added.status_code, 200)
        bad = self._call(
            "post",
            "/items",
            self.manager,
            {"type_id": 1230, "category": "nope"},
        )
        self.assertEqual(bad.status_code, 400)
        off = self._call(
            "patch", "/items/1230", self.manager, {"active": False}
        )
        self.assertFalse(off.json()["active"])
        listing = self._call("get", "/settings", self.manager).json()
        self.assertEqual(listing["items"][0]["name"], "Veldspar")
        gone = self._call("delete", "/items/1230", self.manager)
        self.assertEqual(gone.status_code, 200)
        self.assertFalse(BuybackAcceptedItem.objects.exists())

    def test_type_search(self):
        found = self._call("get", "/types?q=veld", self.manager)
        self.assertEqual(found.json(), [{"type_id": 1230, "name": "Veldspar"}])
