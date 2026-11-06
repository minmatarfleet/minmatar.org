"""Market hub editor: permissions, writes and audit entries."""

from django.contrib.auth.models import Permission, User
from django.test import Client

from app.test import TestCase
from app.testing import auth_headers
from audit.models import AuditEntry
from buyback.tests.helpers import ensure_type
from eveonline.models import EveLocation
from fittings.models import EveDoctrine, EveDoctrineFitting, EveFitting
from market.models import (
    EveMarketContractExpectation,
    EveMarketItemExpectation,
)

BASE = "/api/market/hubs"


class HubEditorTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.hub = EveLocation.objects.create(
            location_id=1234,
            location_name="Amamake Hub",
            short_name="AMA",
            solar_system_id=1,
            solar_system_name="Amamake",
            market_active=True,
        )

    def _manager(self):
        user = User.objects.create(username="manager")
        user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="eveonline",
                codename="change_evelocation",
            )
        )
        return user

    def _call(self, method, path, user, data=None):
        return getattr(self.client, method)(
            f"{BASE}{path}",
            data=data,
            content_type="application/json",
            **auth_headers(user),
        )

    def test_plain_pilot_is_refused_everywhere(self):
        for method, path in (
            ("get", ""),
            ("patch", "/1234"),
            ("delete", "/1234"),
            ("get", "/1234/expectations"),
        ):
            with self.subTest(method=method, path=path):
                response = self._call(method, path, self.user, {})
                self.assertEqual(response.status_code, 403)
        self.assertEqual(AuditEntry.objects.count(), 0)

    def test_anonymous_is_refused(self):
        self.assertEqual(self.client.get(BASE).status_code, 401)

    def test_manager_lists_hubs(self):
        response = self._call("get", "", self._manager())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["location_id"], 1234)

    def test_patch_toggles_sync_and_logs(self):
        manager = self._manager()
        response = self._call(
            "patch", "/1234", manager, {"prices_active": True}
        )
        self.assertEqual(response.status_code, 200)
        self.hub.refresh_from_db()
        self.assertTrue(self.hub.prices_active)
        entry = AuditEntry.objects.get()
        self.assertEqual(entry.user, manager)
        self.assertIn("prices_active=True", entry.summary)

    def test_add_new_hub_needs_names(self):
        manager = self._manager()
        response = self._call("post", "", manager, {"location_id": 99})
        self.assertEqual(response.status_code, 400)
        response = self._call(
            "post",
            "",
            manager,
            {
                "location_id": 99,
                "location_name": "New Hub",
                "solar_system_id": 5,
                "solar_system_name": "Somewhere",
            },
        )
        self.assertEqual(response.status_code, 200)
        created = EveLocation.objects.get(location_id=99)
        self.assertTrue(created.market_active)
        self.assertTrue(created.prices_active)

    def test_remove_hub_keeps_location(self):
        response = self._call("delete", "/1234", self._manager())
        self.assertEqual(response.status_code, 200)
        self.hub.refresh_from_db()
        self.assertFalse(self.hub.market_active)
        self.assertFalse(self.hub.prices_active)

    def test_remove_hub_keeps_the_price_baseline_syncing(self):
        self.hub.price_baseline = True
        self.hub.prices_active = True
        self.hub.save(update_fields=["price_baseline", "prices_active"])
        response = self._call("delete", "/1234", self._manager())
        self.assertEqual(response.status_code, 200)
        self.hub.refresh_from_db()
        self.assertFalse(self.hub.market_active)
        self.assertTrue(self.hub.prices_active)

    def test_item_expectation_add_and_remove(self):
        manager = self._manager()
        ensure_type(
            type_id=34,
            name="Tritanium",
            group_id=18,
            group_name="Mineral",
            category_id=4,
            category_name="Material",
        )
        added = self._call(
            "post", "/1234/expectations/items", manager, {"type_id": 34}
        )
        self.assertEqual(added.status_code, 200)
        self.assertEqual(EveMarketItemExpectation.objects.count(), 1)
        missing = self._call(
            "post", "/1234/expectations/items", manager, {"type_id": 5}
        )
        self.assertEqual(missing.status_code, 404)
        removed = self._call("delete", "/1234/expectations/items/34", manager)
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(EveMarketItemExpectation.objects.count(), 0)

    def test_from_doctrine_tracks_each_fitting_once(self):
        manager = self._manager()
        doctrine = EveDoctrine.objects.create(
            name="Test Doctrine", type="strategic", description="d"
        )
        fit = EveFitting.objects.create(
            name="[NVY-5] Atron",
            ship_id=1,
            description="t",
            eft_format="[Atron, [NVY-5] Atron]",
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine, fitting=fit, role="primary"
        )
        body = {"doctrine_id": doctrine.id}
        first = self._call(
            "post", "/1234/expectations/from-doctrine", manager, body
        )
        self.assertEqual(first.json()["created"], 1)
        second = self._call(
            "post", "/1234/expectations/from-doctrine", manager, body
        )
        self.assertEqual(second.json(), {"created": 0, "already_tracked": 1})
        self.assertEqual(EveMarketContractExpectation.objects.count(), 1)

    def test_type_search_needs_permission(self):
        ensure_type(
            type_id=35,
            name="Pyerite",
            group_id=18,
            group_name="Mineral",
            category_id=4,
            category_name="Material",
        )
        denied = self._call("get", "-type-search?q=pye", self.user)
        self.assertEqual(denied.status_code, 403)
        found = self._call("get", "-type-search?q=pye", self._manager())
        self.assertEqual(found.json(), [{"type_id": 35, "name": "Pyerite"}])
