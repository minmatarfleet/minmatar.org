import json

from django.contrib.auth.models import Permission, User
from django.test import Client
from django.utils import timezone

from app.test import TestCase
from eveonline.models import EveCharacter, EveCharacterAsset, EveLocation
from groups.helpers.feature_access import clear_feature_cache
from industry.models import IndustrySystemCostIndex
from structures import capabilities as caps
from structures import locations as svc
from structures.models import LocationChange

AMAMAKE = 30002537
POLICE_FIT = [
    {
        "name": "Standup XL-Set Ship Manufacturing Efficiency I",
        "slot": "rig",
        "size": "XL",
        "label": "Ship ME",
    },
    {
        "name": "Standup XL-Set Thukker Structure and Component Manufacturing Efficiency",
        "slot": "rig",
        "size": "XL",
        "label": "Components",
    },
    {
        "name": "Standup Manufacturing Plant I",
        "slot": "service",
        "size": "",
        "label": "Manufacturing Plant",
    },
]


class RigDetailsTestCase(TestCase):
    def test_tiers_and_best_tier(self):
        t1 = caps.rig_details(POLICE_FIT[0], 0.4)
        self.assertEqual(
            (t1["tier"], t1["best_tier"], t1["is_best"], t1["use"]),
            ("T1", "T2", False, "subcap"),
        )
        thukker = caps.rig_details(POLICE_FIT[1], 0.4)
        self.assertEqual(
            (thukker["tier"], thukker["is_best"], thukker["use"]),
            ("Faction", True, "components"),
        )
        reactor = caps.rig_details(
            {"name": "Standup L-Set Reactor Efficiency II"}, 0.4
        )
        self.assertEqual((reactor["tier"], reactor["is_best"]), ("T2", True))

    def test_lowsec_bonus_and_upgrade(self):
        t1 = caps.rig_details(POLICE_FIT[0], 0.4)
        self.assertEqual(t1["bonuses"][0]["materials"], 3.8)
        self.assertEqual(t1["bonuses"][0]["time"], 38.0)
        self.assertEqual(t1["upgrade"][0]["materials"], 4.56)
        thukker = caps.rig_details(POLICE_FIT[1], 0.4)
        capital = thukker["bonuses"][0]
        self.assertEqual(capital["category"], "Capital components")
        self.assertEqual(capital["materials"], 7.03)
        self.assertEqual(thukker["upgrade"], [])

    def test_reactor_rigs_ignore_lowsec_multiplier(self):
        bonuses = caps.rig_bonuses("Standup L-Set Reactor Efficiency II", 0.4)
        self.assertEqual(bonuses[0]["materials"], 2.4)

    def test_capital_ship_rig_is_capital_use(self):
        details = caps.rig_details(
            {"name": "Standup XL-Set Capital Ship Manufacturing Efficiency I"},
            0.4,
        )
        self.assertEqual(details["use"], "capital")

    def test_is_industry(self):
        self.assertTrue(caps.is_industry(POLICE_FIT))
        self.assertFalse(
            caps.is_industry(
                [{"name": "Standup Market Hub I", "slot": "service"}]
            )
        )

    def test_facility_tax_only_for_profile_structures(self):
        known = caps.facility_costs(
            "amamake", "Amamake - Police Weapons Facility"
        )
        self.assertEqual(known["facility_tax"], 0.0075)
        self.assertEqual(known["index_discount"], -0.5)
        other = caps.facility_costs("amamake", "Amamake - Somebody's Raitaru")
        self.assertIsNone(other["facility_tax"])
        self.assertEqual(other["index_discount"], -0.5)
        self.assertIsNone(caps.facility_costs(None, "x")["facility_tax"])


class CardCostsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        IndustrySystemCostIndex.objects.create(
            solar_system_id=AMAMAKE,
            manufacturing=0.1309,
            reaction=0.1362,
            invention=0,
            copying=0,
            updated_at=timezone.now(),
        )
        self.location = EveLocation.objects.create(
            location_id=1040000000001,
            location_name="Amamake - Police Weapons Facility",
            solar_system_id=AMAMAKE,
            solar_system_name="Amamake",
            short_name="Police Weapons Facility",
            is_structure=True,
            type_id=35827,
            audience=EveLocation.AUDIENCE_PUBLIC,
            fitting=POLICE_FIT,
        )

    def test_card_shows_costs_rigs_and_services(self):
        response = self.client.get("/api/structures/locations")
        card = response.json()["locations"][0]
        self.assertTrue(card["industry"])
        self.assertEqual(card["manufacturing_index"], 0.1309)
        self.assertEqual(card["reaction_index"], 0.1362)
        self.assertEqual(card["facility_tax"], 0.0075)
        self.assertEqual(card["office_fee_isk"], 50_000_000)
        self.assertEqual(card["rigs"][0]["tier"], "T1")
        self.assertEqual(card["rigs"][1]["use"], "components")
        self.assertEqual(
            card["service_modules"][0]["label"], "Manufacturing Plant"
        )
        self.assertFalse(card["freight_route"])

    def test_detail_lists_planner_systems(self):
        response = self.client.get(
            f"/api/structures/locations/{self.location.location_id}"
        )
        detail = response.json()
        self.assertIn("Amamake", detail["planner_systems"])
        self.assertEqual(detail["planner_facility"], "amamake")
        self.assertEqual(detail["routes_here"], [])


class FreightRouteAndHoldingsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.location = EveLocation.objects.create(
            location_id=1040000000002,
            location_name="Olettiers - Office",
            solar_system_id=1,
            solar_system_name="Olettiers",
            short_name="Olettiers",
            is_structure=True,
        )

    def _grant(self, user, codename, app_label):
        user.user_permissions.add(
            Permission.objects.get(
                codename=codename, content_type__app_label=app_label
            )
        )
        clear_feature_cache()

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def test_freight_route_flag_leaves_freight_off(self):
        self._grant(self.user, "change_evelocation", "eveonline")
        response = self.client.patch(
            f"/api/structures/locations/{self.location.location_id}",
            data=json.dumps({"freight_route_active": True}),
            content_type="application/json",
            **self._auth(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["freight_route"])
        self.assertFalse(response.json()["freight"])
        self.assertTrue(
            LocationChange.objects.filter(
                location=self.location, summary="turned on Freight route"
            ).exists()
        )

    def test_holdings_need_superuser(self):
        self._grant(self.user, "change_evelocation", "eveonline")
        response = self.client.get(
            f"/api/structures/locations/{self.location.location_id}/holdings",
            **self._auth(),
        )
        self.assertEqual(response.status_code, 403)

    def test_holdings_group_alts_under_one_pilot(self):
        self.make_superuser()
        other = User.objects.create(username="other")
        mine = [
            EveCharacter.objects.create(
                character_id=91000001, character_name="Main", user=self.user
            ),
            EveCharacter.objects.create(
                character_id=91000002, character_name="Alt", user=self.user
            ),
        ]
        theirs = EveCharacter.objects.create(
            character_id=91000003, character_name="Other", user=other
        )
        for character, type_name in (
            (mine[0], "Rifter"),
            (mine[0], "Rifter"),
            (mine[1], "Sabre"),
            (theirs, "Rifter"),
        ):
            EveCharacterAsset.objects.create(
                character=character,
                type_id=587 if type_name == "Rifter" else 22456,
                type_name=type_name,
                location_id=self.location.location_id,
                location_name=self.location.location_name,
            )
        response = self.client.get(
            f"/api/structures/locations/{self.location.location_id}/holdings",
            **self._auth(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["items"], 4)
        self.assertEqual(len(data["pilots"]), 2)
        first = data["pilots"][0]
        self.assertEqual(first["items"], 3)
        self.assertEqual(sorted(first["characters"]), ["Alt", "Main"])
        self.assertEqual(first["top_items"][0]["type_name"], "Rifter")
        rifter = data["by_item"][0]
        self.assertEqual((rifter["count"], rifter["holders"]), (3, 2))

    def test_users_name_mains_and_corporations_only(self):
        # pylint: disable=import-outside-toplevel
        from eveonline.helpers.characters import set_primary_character
        from eveonline.models import EveCharacterClone, EveCorporation

        self._grant(self.user, "view_evestructure", "structures")
        EveCorporation.objects.create(corporation_id=98000001, name="Corp A")
        other = User.objects.create(username="other")
        main = EveCharacter.objects.create(
            character_id=91000001,
            character_name="Main",
            corporation_id=98000001,
            user=self.user,
        )
        alt = EveCharacter.objects.create(
            character_id=91000002,
            character_name="Alt",
            corporation_id=98000002,
            user=self.user,
        )
        set_primary_character(self.user, main)
        theirs = EveCharacter.objects.create(
            character_id=91000003,
            character_name="Other",
            corporation_id=98000001,
            user=other,
        )
        set_primary_character(other, theirs)
        EveCharacter.objects.create(
            character_id=91000004, character_name="Elsewhere", user=other
        )
        EveCharacterAsset.objects.create(
            character=alt,
            type_id=587,
            type_name="Rifter",
            location_id=self.location.location_id,
            location_name=self.location.location_name,
        )
        EveCharacterClone.objects.create(
            character=theirs, clone_id=1, location_id=self.location.location_id
        )
        response = self.client.get(
            f"/api/structures/locations/{self.location.location_id}/users",
            **self._auth(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            [p["name"] for p in data["pilots"]], ["Main", "Other"]
        )
        self.assertEqual(
            data["corporations"],
            [{"corporation_id": 98000001, "name": "Corp A", "pilots": 2}],
        )
        self.assertNotIn("Rifter", response.content.decode())
        self.assertNotIn("Alt", response.content.decode())

    def test_users_hidden_when_location_is_not_visible(self):
        response = self.client.get(
            f"/api/structures/locations/{self.location.location_id}/users",
        )
        self.assertEqual(response.status_code, 404)


class SameFittingTestCase(TestCase):
    def test_copied_fit_in_another_system_is_flagged(self):
        EveLocation.objects.create(
            location_id=1040000000003,
            location_name="Amamake - Police Weapons Facility",
            solar_system_id=AMAMAKE,
            solar_system_name="Amamake",
            short_name="Police",
            fitting=POLICE_FIT,
            fitting_scanned_at=timezone.now(),
        )
        EveLocation.objects.create(
            location_id=1050827709022,
            location_name="Auner - Guru Forge",
            solar_system_id=30002059,
            solar_system_name="Auner",
            short_name="Guru Forge",
            fitting=POLICE_FIT,
        )
        items = svc.same_fitting_items(EveLocation.objects.all())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["location_id"], 1050827709022)
        self.assertIn("Police Weapons Facility", items[0]["title"])

    def test_services_only_fit_is_not_flagged(self):
        for location_id, system in ((1, 1), (2, 2)):
            EveLocation.objects.create(
                location_id=location_id,
                location_name=f"S{system} - Hub",
                solar_system_id=system,
                solar_system_name=f"S{system}",
                short_name=f"Hub {system}",
                fitting=[{"name": "Standup Market Hub I", "slot": "service"}],
            )
        self.assertEqual(svc.same_fitting_items(EveLocation.objects.all()), [])
