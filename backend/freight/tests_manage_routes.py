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
