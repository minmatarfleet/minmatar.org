import json
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import Client

from app.test import TestCase
from eveonline.models import EveCharacter, EveCharacterAsset, EveLocation
from groups.helpers.feature_access import clear_feature_cache
from structures import locations as svc
from structures.models import LocationChange, LocationSubmission

SCAN = """Amamake - Police Weapons Facility
Standup XL-Set Ship Manufacturing Efficiency I
Standup XL-Set Thukker Structure and Component Manufacturing Efficiency
Standup XL-Set Laboratory Optimization I
Standup Manufacturing Plant I
Standup Cloning Center I
Standup Stasis Webifier I
Reinforces 20:00"""


class ParsePasteTestCase(TestCase):
    def test_reads_name_fitting_and_reinforce(self):
        parsed = svc.parse_paste(SCAN)
        self.assertEqual(parsed.name, "Amamake - Police Weapons Facility")
        self.assertEqual(parsed.solar_system_name, "Amamake")
        self.assertEqual(parsed.reinforce_hour, 20)
        self.assertEqual(parsed.parts, ["name", "fitting", "reinforce"])
        slots = [m.slot for m in parsed.modules]
        self.assertEqual(slots.count("rig"), 3)
        self.assertEqual(slots.count("service"), 2)
        self.assertEqual(slots.count("defense"), 1)
        labels = [m.label for m in parsed.modules if m.slot == "rig"]
        self.assertEqual(
            labels, ["Ship ME", "Capital components", "Research & invention"]
        )
        self.assertEqual(
            {m.size for m in parsed.modules if m.slot == "rig"}, {"XL"}
        )

    def test_reads_dscan_line(self):
        parsed = svc.parse_paste(
            "35827\tAmamake - Police Weapons Facility\tSotiyo\t12 km"
        )
        self.assertEqual(parsed.type_id, 35827)
        self.assertEqual(parsed.name, "Amamake - Police Weapons Facility")
        self.assertEqual(parsed.parts, ["dscan"])

    def test_strips_selected_item_tail(self):
        parsed = svc.parse_paste(
            "Sosala - WATERMELLON 0 m Reinforced until 2024.06.23 23:20:58"
        )
        self.assertEqual(parsed.name, "Sosala - WATERMELLON")

    def test_rig_labels(self):
        self.assertEqual(
            svc.classify_module("Standup L-Set Reactor Efficiency II").label,
            "Reactor II",
        )
        self.assertEqual(
            svc.classify_module(
                "Standup M-Set Asteroid Ore Grading Processor I"
            ).label,
            "Ore grading",
        )

    def test_rig_groups(self):
        cases = {
            "Standup XL-Set Capital Ship Manufacturing Efficiency I": "capital_production",
            "Standup L-Set Basic Capital Component Manufacturing Efficiency I": "capital_production",
            "Standup M-Set Basic Large Ship Manufacturing Material Efficiency I": "subcap_production",
            "Standup M-Set Equipment Manufacturing Material Efficiency II": "module_production",
            "Standup M-Set Composite Reactor Material Efficiency I": "composite_reactions",
            "Standup M-Set Moon Ore Grading Processor I": "grading",
            "Standup M-Set Reprocessing Monitor I": "reprocessing",
            "Standup M-Set Thermal Armor Reinforcer I": "",
        }
        for name, group in cases.items():
            with self.subTest(name=name):
                self.assertEqual(svc.rig_group(name), group)


class LocationApiTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.location = EveLocation.objects.create(
            location_id=1022167642188,
            location_name="Amamake - 5 times nearly AT winners",
            solar_system_id=30002537,
            solar_system_name="Amamake",
            short_name="Amamake",
            is_structure=True,
            staging_active=True,
            freight_active=True,
            audience=EveLocation.AUDIENCE_ALLIANCE,
        )
        self.public = EveLocation.objects.create(
            location_id=60003760,
            location_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
            solar_system_id=30000142,
            solar_system_name="Jita",
            short_name="Jita",
            audience=EveLocation.AUDIENCE_PUBLIC,
        )

    def _grant(self, codename, app_label):
        self.user.user_permissions.add(
            Permission.objects.get(
                codename=codename, content_type__app_label=app_label
            )
        )
        clear_feature_cache()

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def test_station_card_shows_esi_services(self):
        stations = {
            60003760: (1529, ["market", "cloning", "insurance", "labratory"])
        }
        with patch(
            "structures.location_router._stations", return_value=stations
        ):
            response = self.client.get("/api/structures/locations")
        card = response.json()["locations"][0]
        self.assertEqual(
            [m["label"] for m in card["service_modules"]],
            ["Clone bay", "Research", "Market"],
        )
        self.assertTrue(card["industry"])

    def test_signed_out_sees_public_only(self):
        response = self.client.get("/api/structures/locations")
        self.assertEqual(response.status_code, 200)
        names = [row["short_name"] for row in response.json()["locations"]]
        self.assertEqual(names, ["Jita"])

    def test_new_locations_are_public(self):
        location = EveLocation.objects.create(
            location_id=60008494,
            location_name="Amarr VIII (Oris) - Emperor Family Academy",
            solar_system_id=30002187,
            solar_system_name="Amarr",
            short_name="Amarr",
        )
        self.assertEqual(location.audience, EveLocation.AUDIENCE_PUBLIC)
        response = self.client.get("/api/structures/locations")
        names = [row["short_name"] for row in response.json()["locations"]]
        self.assertIn("Amarr", names)

    def test_migration_opens_default_alliance_locations(self):
        # pylint: disable=import-outside-toplevel
        from importlib import import_module

        from django.apps import apps

        migration = import_module(
            "eveonline.migrations.0119_locations_public_by_default"
        )
        chosen = EveLocation.objects.create(
            location_id=60008494,
            location_name="Amarr VIII (Oris) - Emperor Family Academy",
            solar_system_id=30002187,
            solar_system_name="Amarr",
            short_name="Amarr",
            audience=EveLocation.AUDIENCE_ALLIANCE,
        )
        LocationChange.objects.create(
            location=chosen,
            kind="audience",
            summary="changed who can see it",
        )
        migration.open_default_alliance_locations(apps, None)
        self.location.refresh_from_db()
        chosen.refresh_from_db()
        self.assertEqual(self.location.audience, EveLocation.AUDIENCE_PUBLIC)
        self.assertEqual(chosen.audience, EveLocation.AUDIENCE_ALLIANCE)

    def test_alliance_sees_alliance_locations_and_holdings(self):
        self._grant("view_evestructure", "structures")
        character = EveCharacter.objects.create(
            character_id=91000001, character_name="Pilot", user=self.user
        )
        EveCharacterAsset.objects.create(
            character=character,
            type_id=587,
            type_name="Rifter",
            location_id=self.location.location_id,
            location_name=self.location.location_name,
        )
        response = self.client.get("/api/structures/locations", **self._auth())
        rows = {row["short_name"]: row for row in response.json()["locations"]}
        self.assertIn("Amamake", rows)
        self.assertTrue(rows["Amamake"]["staging"])
        self.assertFalse(rows["Amamake"]["deployment"])
        self.assertEqual(rows["Amamake"]["you"]["items"], 1)
        self.assertTrue(response.json()["can_add"])
        self.assertFalse(response.json()["can_manage"])

    def test_parse_finds_listed_location(self):
        self._grant("view_evestructure", "structures")
        response = self.client.post(
            "/api/structures/locations/parse",
            data=json.dumps({"text": "Amamake - 5 times nearly AT winners"}),
            content_type="application/json",
            **self._auth(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["match"]["status"], "listed")

    def test_parse_finds_id_from_assets(self):
        self._grant("view_evestructure", "structures")
        character = EveCharacter.objects.create(
            character_id=91000002, character_name="Other"
        )
        EveCharacterAsset.objects.create(
            character=character,
            type_id=587,
            type_name="Rifter",
            location_id=1035466617946,
            location_name="Amamake - Police Weapons Facility",
        )
        response = self.client.post(
            "/api/structures/locations/parse",
            data=json.dumps({"text": SCAN}),
            content_type="application/json",
            **self._auth(),
        )
        match = response.json()["match"]
        self.assertEqual(match["status"], "found")
        self.assertEqual(match["source"], "assets")
        self.assertEqual(match["location_id"], 1035466617946)

    @patch(
        "structures.locations._search_with_characters", return_value=(None, "")
    )
    def test_parse_without_id(self, search):
        self._grant("view_evestructure", "structures")
        response = self.client.post(
            "/api/structures/locations/parse",
            data=json.dumps({"text": "Raa - Ru Coalition Hub"}),
            content_type="application/json",
            **self._auth(),
        )
        self.assertEqual(response.json()["match"]["status"], "none")

    @patch("structures.locations._solar_system_id", return_value=30002537)
    def test_submit_and_approve(self, system):
        self._grant("view_evestructure", "structures")
        response = self.client.post(
            "/api/structures/locations/submissions",
            data=json.dumps(
                {
                    "paste_text": SCAN,
                    "name": "Amamake - Police Weapons Facility",
                    "location_id": 1035466617946,
                    "id_source": "assets",
                    "type_id": 35827,
                    "short_name": "Amamake - PWF",
                    "good_for": ["industry"],
                }
            ),
            content_type="application/json",
            **self._auth(),
        )
        self.assertEqual(response.status_code, 201)
        submission_id = response.json()["id"]
        self.assertEqual(response.json()["rig_count"], 3)

        # Pilots can't approve.
        response = self.client.post(
            f"/api/structures/locations/submissions/{submission_id}/approve",
            **self._auth(),
        )
        self.assertEqual(response.status_code, 403)

        self._grant("change_evelocation", "eveonline")
        response = self.client.get(
            "/api/structures/locations/manage/overview", **self._auth()
        )
        self.assertEqual(len(response.json()["submissions"]), 1)

        response = self.client.post(
            f"/api/structures/locations/submissions/{submission_id}/approve",
            **self._auth(),
        )
        self.assertEqual(response.status_code, 200)
        location = EveLocation.objects.get(location_id=1035466617946)
        self.assertEqual(location.audience, EveLocation.AUDIENCE_PUBLIC)
        self.assertEqual(location.type_id, 35827)
        self.assertEqual(location.reinforce_hour, 20)
        self.assertEqual(len(location.fitting), 6)
        self.assertEqual(location.short_name, "Amamake - PWF")
        kinds = list(
            LocationChange.objects.filter(location=location).values_list(
                "kind", flat=True
            )
        )
        self.assertCountEqual(kinds, ["added", "fitting", "approved"])
        self.assertEqual(
            LocationSubmission.objects.get(id=submission_id).status,
            LocationSubmission.STATUS_APPROVED,
        )

    def test_cannot_approve_without_id(self):
        self._grant("change_evelocation", "eveonline")
        row = LocationSubmission.objects.create(
            name="Raa - Ru Coalition Hub", submitted_by=self.user
        )
        response = self.client.post(
            f"/api/structures/locations/submissions/{row.id}/approve",
            **self._auth(),
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_records_history(self):
        self._grant("change_evelocation", "eveonline")
        response = self.client.patch(
            f"/api/structures/locations/{self.location.location_id}",
            data=json.dumps(
                {
                    "description": "Home",
                    "audience": "public",
                    "fleets_active": True,
                    "reinforce_hour": 19,
                }
            ),
            content_type="application/json",
            **self._auth(),
        )
        self.assertEqual(response.status_code, 200)
        self.location.refresh_from_db()
        self.assertEqual(self.location.audience, "public")
        self.assertTrue(self.location.fleets_active)
        summaries = list(
            LocationChange.objects.filter(location=self.location).values_list(
                "summary", flat=True
            )
        )
        self.assertIn("edited About", summaries)
        self.assertIn("changed who can see it", summaries)
        self.assertIn("turned on Fleet form-up", summaries)
        detail = response.json()
        self.assertEqual(len(detail["changes"]), len(summaries))

    def test_deployment_flag_and_rig_groups_on_cards(self):
        self._grant("view_evestructure", "structures")
        self._grant("change_evelocation", "eveonline")
        self.public.fitting = [
            {
                "name": "Standup L-Set Equipment Manufacturing Efficiency I",
                "slot": "rig",
                "size": "L",
                "label": "Equipment",
            }
        ]
        self.public.save()
        response = self.client.patch(
            f"/api/structures/locations/{self.public.location_id}",
            data=json.dumps({"deployment_active": True}),
            content_type="application/json",
            **self._auth(),
        )
        self.assertEqual(response.status_code, 200)
        self.public.refresh_from_db()
        self.assertTrue(self.public.deployment_active)
        self.assertTrue(
            LocationChange.objects.filter(
                location=self.public, summary="turned on Deployment"
            ).exists()
        )
        rows = {
            row["short_name"]: row
            for row in self.client.get(
                "/api/structures/locations", **self._auth()
            ).json()["locations"]
        }
        self.assertTrue(rows["Jita"]["deployment"])
        self.assertEqual(rows["Jita"]["rigs"][0]["group"], "module_production")
        self.assertEqual(list(rows)[:2], ["Amamake", "Jita"])

    def test_patch_needs_manage(self):
        self._grant("view_evestructure", "structures")
        response = self.client.patch(
            f"/api/structures/locations/{self.location.location_id}",
            data=json.dumps({"description": "x"}),
            content_type="application/json",
            **self._auth(),
        )
        self.assertEqual(response.status_code, 403)

    def test_new_fitting_records_diff(self):
        self._grant("view_evestructure", "structures")
        self.location.fitting = svc.modules_as_json(
            svc.parse_paste(SCAN).modules[:2]
        )
        self.location.save()
        response = self.client.post(
            f"/api/structures/locations/{self.location.location_id}/fitting",
            data=json.dumps({"text": SCAN}),
            content_type="application/json",
            **self._auth(),
        )
        self.assertEqual(response.status_code, 200)
        change = LocationChange.objects.get(
            location=self.location, kind="fitting"
        )
        self.assertEqual(len(change.details["added"]), 4)

    def test_attention_flags_duplicate_short_names(self):
        EveLocation.objects.create(
            location_id=1051465618860,
            location_name="R-6KYM - DO NOT USE",
            solar_system_id=1,
            solar_system_name="R-6KYM",
            short_name="R-6KYM",
        )
        EveLocation.objects.create(
            location_id=1053229023468,
            location_name="R-6KYM - Casper Anchored It",
            solar_system_id=1,
            solar_system_name="R-6KYM",
            short_name="R-6KYM",
        )
        items = svc.attention_items(EveLocation.objects.all())
        self.assertIn("duplicate_short_name", [item["kind"] for item in items])


class RetireLocationTestCase(TestCase):
    """Retiring hides a location without touching what points at it, and
    approving the same structure again brings the same row back."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.staging = EveLocation.objects.create(
            location_id=1022167642188,
            location_name="Amamake - 5 times nearly AT winners",
            solar_system_id=30002537,
            solar_system_name="Amamake",
            short_name="Amamake",
            is_structure=True,
            staging_active=True,
            freight_active=True,
        )
        self.spoke = EveLocation.objects.create(
            location_id=1035466617946,
            location_name="Auga - Old Spoke",
            solar_system_id=30002538,
            solar_system_name="Auga",
            short_name="Auga",
            is_structure=True,
            freight_active=True,
            fleets_active=True,
            market_active=True,
            prices_active=True,
        )

    def _manager(self):
        self.user.user_permissions.add(
            Permission.objects.get(
                codename="change_evelocation",
                content_type__app_label="eveonline",
            )
        )
        clear_feature_cache()

    def _retire(self, location_id):
        return self.client.post(
            f"/api/structures/locations/{location_id}/retire",
            data=json.dumps({"reason": "Unanchoring"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    def test_needs_manage(self):
        self.assertEqual(self._retire(self.spoke.location_id).status_code, 403)
        self.assertTrue(EveLocation.objects.filter(pk=self.spoke.pk).exists())

    def test_staging_cannot_be_retired(self):
        self._manager()
        self.assertEqual(
            self._retire(self.staging.location_id).status_code, 400
        )
        self.assertTrue(
            EveLocation.objects.filter(pk=self.staging.pk).exists()
        )

    def test_retire_keeps_fleets_and_stops_routes(self):
        # pylint: disable=import-outside-toplevel
        from fleets.models import EveFleet
        from freight.models import EveFreightRoute
        from fittings.helpers.change_request_display import (
            _location_name_map,
        )

        self._manager()
        fleet = EveFleet.objects.create(
            start_time="2026-11-01T19:00:00Z",
            description="Old roam",
            type="training",
            status="complete",
            created_by=self.user,
            location=self.spoke,
        )
        route = EveFreightRoute.objects.create(
            origin_location=self.staging, destination_location=self.spoke
        )

        response = self._retire(self.spoke.location_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Auga - Old Spoke")

        # Gone from the site and the manage list.
        self.assertFalse(EveLocation.objects.filter(pk=self.spoke.pk).exists())
        overview = self.client.get(
            "/api/structures/locations/manage/overview",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        ).json()
        self.assertNotIn(
            self.spoke.location_id,
            [row["location_id"] for row in overview["locations"]],
        )
        self.assertEqual(
            self.client.get(
                f"/api/structures/locations/{self.spoke.location_id}"
            ).status_code,
            404,
        )

        # Still there for the fleet and for name lookups.
        fleet = EveFleet.objects.get(pk=fleet.pk)
        self.assertEqual(fleet.location_id, self.spoke.location_id)
        self.assertEqual(fleet.location.location_name, "Auga - Old Spoke")
        self.assertEqual(
            _location_name_map([self.spoke.location_id]),
            {self.spoke.location_id: "Auga"},
        )

        # Site settings are off and its routes stopped.
        retired = EveLocation.all_objects.get(pk=self.spoke.pk)
        self.assertIsNotNone(retired.deleted)
        self.assertFalse(retired.freight_active)
        self.assertFalse(retired.fleets_active)
        self.assertFalse(retired.market_active)
        self.assertFalse(retired.prices_active)
        route.refresh_from_db()
        self.assertFalse(route.active)
        change = LocationChange.objects.filter(location=retired).first()
        self.assertEqual(change.kind, "retired")
        self.assertEqual(change.details["reason"], "Unanchoring")

    @patch("structures.locations._solar_system_id", return_value=30002538)
    def test_approving_again_restores_the_same_row(self, system):
        # pylint: disable=import-outside-toplevel
        from fleets.models import EveFleet

        self._manager()
        fleet = EveFleet.objects.create(
            start_time="2026-11-01T19:00:00Z",
            description="Old roam",
            type="training",
            status="complete",
            created_by=self.user,
            location=self.spoke,
        )
        self.assertEqual(self._retire(self.spoke.location_id).status_code, 200)

        # A pilot submits it again; it is not "already listed".
        match = svc.find_structure(self.user, "Auga - Old Spoke")
        self.assertNotEqual(match.status, "listed")
        submission = LocationSubmission.objects.create(
            name="Auga - Back Again",
            location_id=self.spoke.location_id,
            short_name="Auga II",
            submitted_by=self.user,
        )
        response = self.client.post(
            f"/api/structures/locations/submissions/{submission.id}/approve",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)

        location = EveLocation.objects.get(pk=self.spoke.pk)
        self.assertIsNone(location.deleted)
        self.assertEqual(location.location_name, "Auga - Back Again")
        self.assertEqual(location.short_name, "Auga II")
        # Comes back clean: nothing switched on.
        self.assertFalse(location.freight_active)
        self.assertFalse(location.fleets_active)
        self.assertFalse(location.market_active)
        self.assertEqual(
            EveLocation.all_objects.filter(pk=self.spoke.pk).count(), 1
        )
        self.assertEqual(
            EveFleet.objects.get(pk=fleet.pk).location_id,
            self.spoke.location_id,
        )
        kinds = list(
            LocationChange.objects.filter(location=location).values_list(
                "kind", flat=True
            )
        )
        self.assertIn("retired", kinds)
        self.assertIn("restored", kinds)
        self.assertNotIn("added", kinds)
