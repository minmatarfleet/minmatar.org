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

    def test_items_show_what_they_pay_now(self):
        settings = EveBuybackSettings.load()
        settings.demand_jita_buy = 1.0
        settings.surplus_jita_buy = 0.9
        settings.location = self.location
        settings.save()
        scordite = ensure_type(
            type_id=1228,
            name="Scordite",
            group_id=460,
            group_name="Scordite",
            category_id=25,
            category_name="Asteroid",
        )
        BuybackAcceptedItem.objects.create(
            eve_type=self.veldspar,
            category="ore",
            demand_status=BuybackAcceptedItem.DemandStatus.HIGH,
        )
        BuybackAcceptedItem.objects.create(eve_type=scordite, category="ore")
        BuybackAcceptedItem.objects.filter(eve_type=scordite).update(
            active=False
        )
        body = self._call("get", "/settings", self.manager).json()
        self.assertEqual(body["location_name"], "Buyback Hub")
        items = {item["name"]: item for item in body["items"]}
        self.assertEqual(items["Veldspar"]["pays_rate"], 1.0)
        self.assertEqual(items["Veldspar"]["demand_label"], "High")
        self.assertEqual(items["Veldspar"]["category_label"], "Ore")
        self.assertIsNone(items["Scordite"]["pays_rate"])

        BuybackAcceptedItem.objects.filter(eve_type=scordite).update(
            active=True
        )
        body = self._call("get", "/settings", self.manager).json()
        items = {item["name"]: item for item in body["items"]}
        self.assertEqual(items["Scordite"]["pays_rate"], 0.9)

    def test_new_item_category_comes_from_its_group(self):
        tritanium = ensure_type(
            type_id=2393,
            name="Bacteria",
            group_id=1042,
            group_name="Basic Commodities - Tier 1",
            category_id=43,
            category_name="Planetary Commodities",
        )
        rifter = ensure_type(
            type_id=587,
            name="Rifter",
            group_id=25,
            group_name="Frigate",
            category_id=6,
            category_name="Ship",
        )
        ore = self._call("post", "/items", self.manager, {"type_id": 1230})
        self.assertEqual(ore.status_code, 200, ore.content)
        self.assertEqual(ore.json()["category"], "ore")
        p1 = self._call(
            "post", "/items", self.manager, {"type_id": tritanium.id}
        )
        self.assertEqual(p1.json()["category"], "p1")
        ship = self._call(
            "post", "/items", self.manager, {"type_id": rifter.id}
        )
        self.assertEqual(ship.status_code, 400)
        self.assertIn("pick its category", ship.json()["detail"])
        picked = self._call(
            "post",
            "/items",
            self.manager,
            {"type_id": rifter.id, "category": "p4"},
        )
        self.assertEqual(picked.json()["category"], "p4")
