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
        self.assertEqual(labels, ["Ship ME", "Components", "Lab"])
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

    def test_signed_out_sees_public_only(self):
        response = self.client.get("/api/structures/locations")
        self.assertEqual(response.status_code, 200)
        names = [row["short_name"] for row in response.json()["locations"]]
        self.assertEqual(names, ["Jita"])

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
