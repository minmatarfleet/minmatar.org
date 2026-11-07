"""Freight route editor: permissions, validation, audit."""

from django.contrib.auth.models import Permission, User
from django.test import Client

from app.test import TestCase
from app.testing import auth_headers
from audit.models import AuditEntry
from eveonline.models import EveLocation
from freight.models import EveFreightRoute

BASE = "/api/freight/manage/routes"


class FreightManageTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.manager = User.objects.create(username="freight_manager")
        self.manager.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="freight",
                codename="change_evefreightroute",
            )
        )
        self.jita = self._location(1, "Jita", "JITA")
        self.amo = self._location(2, "Amamake", "AMA")

    def _location(self, location_id, name, short):
        return EveLocation.objects.create(
            location_id=location_id,
            location_name=name,
            short_name=short,
            solar_system_id=location_id,
            solar_system_name=name,
            freight_active=True,
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
            ("get", "", {}),
            (
                "post",
                "",
                {"origin_location_id": 1, "destination_location_id": 2},
            ),
            ("patch", "/1", {}),
        ):
            with self.subTest(method=method):
                response = self._call(method, path, self.user, body)
                self.assertEqual(response.status_code, 403)
        self.assertEqual(AuditEntry.objects.count(), 0)

    def test_add_edit_and_retire_a_route(self):
        created = self._call(
            "post",
            "",
            self.manager,
            {
                "origin_location_id": 1,
                "destination_location_id": 2,
                "isk_per_m3": 400,
                "collateral_modifier": 0.01,
            },
        )
        self.assertEqual(created.status_code, 200)
        route_id = created.json()["route_id"]
        edited = self._call(
            "patch", f"/{route_id}", self.manager, {"isk_per_m3": 450}
        )
        self.assertEqual(edited.json()["isk_per_m3"], 450)
        retired = self._call(
            "patch", f"/{route_id}", self.manager, {"active": False}
        )
        self.assertFalse(retired.json()["active"])
        self.assertFalse(EveFreightRoute.objects.available().exists())
        listing = self._call("get", "", self.manager).json()
        self.assertEqual(len(listing["routes"]), 1)
        self.assertEqual(len(listing["locations"]), 2)
        self.assertEqual(AuditEntry.objects.count(), 3)

    def test_empty_cap_clears_the_limit(self):
        created = self._call(
            "post",
            "",
            self.manager,
            {
                "origin_location_id": 1,
                "destination_location_id": 2,
                "max_m3": 1000,
                "max_collateral": 500,
            },
        )
        route_id = created.json()["route_id"]
        cleared = self._call(
            "patch",
            f"/{route_id}",
            self.manager,
            {"max_m3": None, "max_collateral": None},
        )
        self.assertEqual(cleared.status_code, 200, cleared.content)
        body = cleared.json()
        self.assertIsNone(body["max_m3"])
        self.assertIsNone(body["max_collateral"])

    def test_same_origin_and_destination_is_rejected(self):
        response = self._call(
            "post",
            "",
            self.manager,
            {"origin_location_id": 1, "destination_location_id": 1},
        )
        self.assertEqual(response.status_code, 400)

    def test_route_to_a_closed_location_cannot_be_active(self):
        self.amo.freight_active = False
        self.amo.save()
        response = self._call(
            "post",
            "",
            self.manager,
            {"origin_location_id": 1, "destination_location_id": 2},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EveFreightRoute.objects.exists())

    def test_fixed_route_flags_an_xl_fee_that_never_applies(self):
        created = self._call(
            "post",
            "",
            self.manager,
            {
                "origin_location_id": 1,
                "destination_location_id": 2,
                "route_type": "fixed",
                "fixed_fee_millions": 95,
                "xl_fee_millions": 40,
                "max_m3": 350_000,
                "max_collateral": 5_000_000_000,
            },
        )
        self.assertEqual(created.status_code, 200, created.content)
        body = created.json()
        self.assertTrue(body["fee_never_applies"])
        self.assertEqual(
            body["quote"],
            {
                "m3": 200_000,
                "collateral": 2_000_000_000,
                "cost": 95_000_000,
                "fee_never_applies": True,
            },
        )
        raised = self._call(
            "patch", f"/{body['route_id']}", self.manager, {"max_m3": 900_000}
        )
        self.assertFalse(raised.json()["fee_never_applies"])

    def test_quote_prices_unsaved_values(self):
        payload = {
            "route_type": "rate",
            "isk_per_m3": 420,
            "collateral_modifier": 0.012,
        }
        self.assertEqual(
            self._call("post", "/quote", self.user, payload).status_code, 403
        )
        response = self._call("post", "/quote", self.manager, payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response.json(),
            {
                "m3": 200_000,
                "collateral": 2_000_000_000,
                "cost": 420 * 200_000 + 24_000_000,
                "fee_never_applies": False,
            },
        )
        # A small cap cuts the sample to the route's limits.
        capped = self._call(
            "post",
            "/quote",
            self.manager,
            {
                "route_type": "fixed",
                "fixed_fee_millions": 10,
                "max_m3": 60_000,
                "max_collateral": 1_000_000_000,
            },
        ).json()
        self.assertEqual(
            (capped["m3"], capped["collateral"], capped["cost"]),
            (60_000, 1_000_000_000, 10_000_000),
        )
        bad = self._call(
            "post", "/quote", self.manager, {"route_type": "teleport"}
        )
        self.assertEqual(bad.status_code, 400)
        self.assertFalse(EveFreightRoute.objects.exists())
