"""Industry delivery switch and Who can dock on the location settings."""

import json
from types import SimpleNamespace

from django.contrib.auth.models import Permission
from django.test import Client

from app.test import TestCase
from eveonline.models import EveAlliance, EveCorporation, EveLocation
from groups.helpers.feature_access import clear_feature_cache
from structures import dock_access
from structures.models import LocationChange


class DockAccessHelperTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.alliance = EveAlliance.objects.create(
            alliance_id=99000001, name="Example Alliance", ticker="EXA"
        )
        self.corp = EveCorporation.objects.create(
            corporation_id=98000001, name="Example Builders", ticker="EXB"
        )

    def test_resolves_names_and_tickers_locally(self):
        entries, unknown = dock_access.resolve_dock_names(
            ["exa", "Example Builders", "EXB", "Nobody Here", " "]
        )
        self.assertEqual(
            [(e["kind"], e["id"], e["ticker"]) for e in entries],
            [("alliance", 99000001, "EXA"), ("corporation", 98000001, "EXB")],
        )
        self.assertEqual(unknown, ["Nobody Here"])

    def test_character_can_dock_by_corp_or_alliance(self):
        location = SimpleNamespace(dock_access=[])
        outsider = SimpleNamespace(corporation_id=1, alliance_id=2)
        self.assertTrue(dock_access.character_can_dock(location, outsider))

        location.dock_access = [
            {"kind": "corporation", "id": 98000001, "name": "EB"},
            {"kind": "alliance", "id": 99000001, "name": "EA"},
            "junk",
        ]
        self.assertFalse(dock_access.character_can_dock(location, outsider))
        self.assertTrue(
            dock_access.character_can_dock(
                location, SimpleNamespace(corporation_id=98000001)
            )
        )
        self.assertTrue(
            dock_access.character_can_dock(
                location,
                SimpleNamespace(corporation_id=5, alliance_id=99000001),
            )
        )
        self.assertEqual(dock_access.dock_tickers(location), ["EB", "EA"])


class LocationDockSettingsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.staging = EveLocation.objects.create(
            location_id=1000000001,
            location_name="Home Station",
            solar_system_id=30002537,
            solar_system_name="Amamake",
            short_name="Home",
            staging_active=True,
            industry_delivery=True,
        )
        self.forward = EveLocation.objects.create(
            location_id=1000000002,
            location_name="Forward Station",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="Forward",
            fleets_active=True,
        )
        EveCorporation.objects.create(
            corporation_id=98000001, name="Example Builders", ticker="EXB"
        )
        for codename, app_label in (
            ("view_evestructure", "structures"),
            ("change_evelocation", "eveonline"),
        ):
            self.user.user_permissions.add(
                Permission.objects.get(
                    codename=codename, content_type__app_label=app_label
                )
            )
        clear_feature_cache()

    def _patch(self, body):
        return self.client.patch(
            f"/api/structures/locations/{self.forward.location_id}",
            data=json.dumps(body),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    def test_industry_delivery_switch_records_a_change(self):
        response = self._patch({"industry_delivery": True})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["industry_delivery"])
        self.forward.refresh_from_db()
        self.assertTrue(self.forward.industry_delivery)
        self.assertTrue(
            LocationChange.objects.filter(
                location=self.forward,
                summary="turned on Industry delivery",
            ).exists()
        )

    def test_dock_access_resolves_names_and_records_a_change(self):
        response = self._patch({"dock_access_names": ["EXB"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["dock_access"],
            [
                {
                    "kind": "corporation",
                    "id": 98000001,
                    "name": "Example Builders",
                    "ticker": "EXB",
                }
            ],
        )
        change = LocationChange.objects.get(
            location=self.forward, kind="dock_access"
        )
        self.assertEqual(change.details, {"from": [], "to": ["EXB"]})

        # Same list again: nothing recorded. Empty list: anyone again.
        self._patch({"dock_access_names": ["Example Builders"]})
        self.assertEqual(
            LocationChange.objects.filter(kind="dock_access").count(), 1
        )
        self._patch({"dock_access_names": []})
        self.forward.refresh_from_db()
        self.assertEqual(self.forward.dock_access, [])

    def test_unknown_dock_name_is_rejected(self):
        response = self._patch({"dock_access_names": ["Nobody Here"]})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Nobody Here", response.json()["detail"])
        self.forward.refresh_from_db()
        self.assertEqual(self.forward.dock_access, [])

    def test_leaving_dock_access_out_keeps_it(self):
        self._patch({"dock_access_names": ["EXB"]})
        self._patch({"description": "Forward base"})
        self.forward.refresh_from_db()
        self.assertEqual(len(self.forward.dock_access), 1)

    def test_retire_clears_industry_delivery(self):
        self.forward.industry_delivery = True
        self.forward.save()
        response = self.client.post(
            f"/api/structures/locations/{self.forward.location_id}/retire",
            data=json.dumps({"reason": ""}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        retired = EveLocation.all_objects.get(pk=self.forward.pk)
        self.assertFalse(retired.industry_delivery)
        change = LocationChange.objects.get(location=retired, kind="retired")
        self.assertIn("industry_delivery", change.details["turned_off"])
