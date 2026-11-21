"""Universe: structure visibility, reports, the global timerboard and moons."""

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, Group, User
from django.db.models import signals
from django.test import Client
from django.utils import timezone
from eveuniverse.models import EveConstellation, EveRegion, EveSolarSystem

from app.test import TestCase
from app.testing import make_token
from eveonline.constants import MINMATAR_FLEET_ALLIANCE_ID
from eveonline.models import EveAlliance, EveCharacter, EveCorporation
from groups.models import AffiliationType, UserAffiliation
from moons.models import EveMoon, EveMoonDistribution, EveMoonScan
from structures.models import EveStructure, EveStructureTimer
from structures.reported import (
    ReportDetails,
    absorb_reported_structure,
    normalise_name,
    record_report,
)
from universe.access import (
    can_change_visibility,
    can_see_moon_contents,
    can_see_structure,
    visible_structures,
)

ALLOW = "universe.router.can_use_feature"

AMAMAKE = 30002537
TU_O0T = 30001111


def _system(system_id, name):
    region, _ = EveRegion.objects.get_or_create(
        id=10000030, defaults={"name": "Heimatar"}
    )
    constellation, _ = EveConstellation.objects.get_or_create(
        id=20000334,
        defaults={
            "name": "Anher",
            "eve_region": region,
            "position_x": 0.0,
            "position_y": 0.0,
            "position_z": 0.0,
        },
    )
    return EveSolarSystem.objects.get_or_create(
        id=system_id,
        defaults={
            "name": name,
            "eve_constellation": constellation,
            "security_status": 0.4,
            "position_x": 0.0,
            "position_y": 0.0,
            "position_z": 0.0,
            "enabled_sections": 0,
        },
    )[0]


class UniverseFixture(TestCase):
    """Two alliance corporations and one outside, with a pilot for each
    role the visibility rules care about."""

    def setUp(self):
        super().setUp()
        # Creating groups and affiliations would call Discord, as in
        # groups.tests.test_feature_access.
        signals.post_save.disconnect(
            sender=Group, dispatch_uid="group_post_save"
        )
        signals.m2m_changed.disconnect(
            sender=User.groups.through, dispatch_uid="user_group_changed"
        )
        self.client = Client()
        _system(AMAMAKE, "Amamake")
        _system(TU_O0T, "TU-O0T")
        alliance = EveAlliance.objects.create(
            alliance_id=MINMATAR_FLEET_ALLIANCE_ID,
            name="Minmatar Fleet Alliance",
        )
        self.corp = EveCorporation.objects.create(
            corporation_id=2001, name="Rattini Tribe", alliance=alliance
        )
        self.sibling = EveCorporation.objects.create(
            corporation_id=2002, name="Soltech Armada", alliance=alliance
        )
        group = Group.objects.create(name="Alliance")
        self.alliance_affiliation = AffiliationType.objects.create(
            name="Alliance", group=group, priority=10
        )
        self.pilots = {
            "superuser": self._pilot("superuser", superuser=True),
            "director": self._pilot("director", corp=self.corp, director=True),
            "steward": self._pilot("steward", corp=self.corp, steward=True),
            "alt_director": self._pilot("alt_director", corp=self.sibling),
            "member": self._pilot("member", corp=self.corp),
            "sibling_member": self._pilot("sibling_member", corp=self.sibling),
            "sibling_steward": self._pilot(
                "sibling_steward", corp=self.sibling, steward_of=self.sibling
            ),
            "outsider": self._pilot("outsider", corp=None, alliance=False),
        }
        # The alt director's main is in the sibling corp; an alt is a
        # director of Rattini Tribe.
        alt = EveCharacter.objects.create(
            character_id=9001,
            character_name="Alt",
            corporation_id=self.corp.corporation_id,
            user=self.pilots["alt_director"],
        )
        self.corp.directors.add(alt)
        self.structures = {
            visibility: self._esi_structure(index, visibility)
            for index, visibility in enumerate(
                ["alliance", "corporation", "private"], start=1
            )
        }
        self.reported = EveStructure.objects.create(
            id=EveStructure.REPORTED_ID_BASE,
            system_id=TU_O0T,
            system_name="TU-O0T",
            type_id=35832,
            type_name="Astrahus",
            name="Cerulean Cave",
            owner_corporation_name="Veritas Holdings",
            visibility="alliance",
            source="reported",
        )

    _next_character = 100

    def _pilot(
        self,
        name,
        corp=None,
        superuser=False,
        director=False,
        steward=False,
        steward_of=None,
        alliance=True,
    ):
        user = User.objects.create(username=name, is_superuser=superuser)
        if alliance:
            UserAffiliation.objects.create(
                user=user, affiliation=self.alliance_affiliation
            )
        UniverseFixture._next_character += 1
        character = EveCharacter.objects.create(
            character_id=UniverseFixture._next_character,
            character_name=name.title(),
            corporation_id=corp.corporation_id if corp else 3999,
            user=user,
        )
        if director:
            corp.directors.add(character)
        if steward:
            corp.stewards.add(character)
        if steward_of:
            steward_of.stewards.add(character)
        return user

    def _esi_structure(self, index, visibility):
        return EveStructure.objects.create(
            id=1000 + index,
            system_id=AMAMAKE,
            system_name="Amamake",
            type_id=35833,
            type_name="Fortizar",
            name=f"Amamake - {visibility}",
            reinforce_hour=19,
            corporation=self.corp,
            visibility=visibility,
        )

    def get(self, user, url):
        return self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {make_token(user)}"
        )

    def send(self, user, method, url, payload):
        return getattr(self.client, method)(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {make_token(user)}",
        )


# Who sees which structure. Reported rows are always alliance-wide.
MATRIX = {
    "superuser": {"alliance", "corporation", "private", "reported"},
    "director": {"alliance", "corporation", "private", "reported"},
    "steward": {"alliance", "corporation", "private", "reported"},
    "alt_director": {"alliance", "corporation", "private", "reported"},
    "member": {"alliance", "corporation", "reported"},
    "sibling_member": {"alliance", "reported"},
    "sibling_steward": {"alliance", "reported"},
    "outsider": set(),
}


class VisibilityTests(UniverseFixture):
    def _rows(self):
        return {**self.structures, "reported": self.reported}

    def test_visibility_matrix(self):
        for pilot, expected in MATRIX.items():
            user = self.pilots[pilot]
            for key, structure in self._rows().items():
                with self.subTest(pilot=pilot, structure=key):
                    self.assertEqual(
                        can_see_structure(user, structure), key in expected
                    )

    def test_queryset_matches_row_check(self):
        for pilot, user in self.pilots.items():
            visible = set(
                visible_structures(user).values_list("id", flat=True)
            )
            for key, structure in self._rows().items():
                with self.subTest(pilot=pilot, structure=key):
                    self.assertEqual(
                        structure.id in visible,
                        can_see_structure(user, structure),
                    )

    def test_anonymous_sees_nothing(self):
        self.assertEqual(visible_structures(AnonymousUser()).count(), 0)

    def test_only_owning_managers_change_visibility(self):
        private = self.structures["private"]
        self.assertTrue(
            can_change_visibility(self.pilots["director"], private)
        )
        self.assertTrue(can_change_visibility(self.pilots["steward"], private))
        self.assertTrue(
            can_change_visibility(self.pilots["alt_director"], private)
        )
        self.assertTrue(
            can_change_visibility(self.pilots["superuser"], private)
        )
        self.assertFalse(can_change_visibility(self.pilots["member"], private))
        self.assertFalse(
            can_change_visibility(self.pilots["sibling_steward"], private)
        )
        # Reported structures stay alliance-wide.
        self.assertFalse(
            can_change_visibility(self.pilots["superuser"], self.reported)
        )


@patch(ALLOW, return_value=True)
class StructureApiTests(UniverseFixture):
    def test_list_returns_only_visible(self, _):
        response = self.get(self.pilots["member"], "/api/universe/structures")
        self.assertEqual(response.status_code, 200)
        names = {row["name"] for row in response.json()["structures"]}
        self.assertEqual(
            names,
            {"Amamake - alliance", "Amamake - corporation", "Cerulean Cave"},
        )

    def test_hidden_structure_is_404(self, _):
        private = self.structures["private"]
        response = self.get(
            self.pilots["member"], f"/api/universe/structures/{private.id}"
        )
        self.assertEqual(response.status_code, 404)

    def test_manager_changes_visibility(self, _):
        private = self.structures["private"]
        response = self.send(
            self.pilots["steward"],
            "patch",
            f"/api/universe/structures/{private.id}/visibility",
            {"visibility": "alliance"},
        )
        self.assertEqual(response.status_code, 200)
        private.refresh_from_db()
        self.assertEqual(private.visibility, "alliance")

    def test_member_cannot_change_visibility(self, _):
        corp_only = self.structures["corporation"]
        response = self.send(
            self.pilots["member"],
            "patch",
            f"/api/universe/structures/{corp_only.id}/visibility",
            {"visibility": "alliance"},
        )
        self.assertEqual(response.status_code, 403)

    def test_hidden_visibility_change_is_404(self, _):
        private = self.structures["private"]
        response = self.send(
            self.pilots["sibling_steward"],
            "patch",
            f"/api/universe/structures/{private.id}/visibility",
            {"visibility": "alliance"},
        )
        self.assertEqual(response.status_code, 404)

    def test_match_offers_only_visible_candidates(self, _):
        response = self.send(
            self.pilots["member"],
            "post",
            "/api/universe/structures/match",
            {"system_name": "Amamake", "type_id": 35833, "name": ""},
        )
        names = {row["name"] for row in response.json()["candidates"]}
        self.assertNotIn("Amamake - private", names)
        self.assertIn("Amamake - corporation", names)

    def test_report_on_hidden_row_updates_it_silently(self, _):
        private = self.structures["private"]
        private.fitting = None
        private.save()
        response = self.send(
            self.pilots["sibling_member"],
            "post",
            "/api/universe/structures/report",
            {
                "system_name": "Amamake",
                "type_id": 35833,
                "name": "Amamake - private",
                "fitting": "Standup Market Hub I",
            },
        )
        self.assertEqual(response.json(), {"status": "recorded"})
        private.refresh_from_db()
        self.assertEqual(private.fitting, "Standup Market Hub I")
        self.assertEqual(private.visibility, "private")
        self.assertEqual(private.source, "esi")
        self.assertEqual(
            EveStructure.objects.filter(source="reported").count(), 1
        )

    def test_new_report_gets_a_reported_id(self, _):
        response = self.send(
            self.pilots["member"],
            "post",
            "/api/universe/structures/report",
            {
                "system_name": "TU-O0T",
                "type_id": 35833,
                "name": "TU-O0T - Forward Post",
                "corporation_name": "Rattini Tribe",
                "reinforce_hour": 3,
            },
        )
        self.assertEqual(response.status_code, 200)
        row = EveStructure.objects.get(name="TU-O0T - Forward Post")
        self.assertLess(row.id, EveStructure.REPORTED_ID_BASE)
        self.assertEqual(row.visibility, "alliance")
        self.assertEqual(row.corporation, self.corp)
        self.assertIsNone(row.esi_structure_id)

    def test_report_with_unknown_system_is_400(self, _):
        response = self.send(
            self.pilots["member"],
            "post",
            "/api/universe/structures/report",
            {"system_name": "Nowhere", "type_id": 35833},
        )
        self.assertEqual(response.status_code, 400)

    def test_confirm_marks_last_seen(self, _):
        response = self.send(
            self.pilots["member"],
            "post",
            f"/api/universe/structures/{self.reported.id}/confirm",
            {},
        )
        self.assertEqual(response.status_code, 200)
        self.reported.refresh_from_db()
        self.assertEqual(
            self.reported.last_confirmed_by, self.pilots["member"]
        )


class ReportRulesTests(UniverseFixture):
    def test_normalise_name_strips_system_prefix(self):
        self.assertEqual(
            normalise_name("  TU-O0T -  Cerulean   Cave ", "TU-O0T"),
            "cerulean cave",
        )

    def test_report_never_overwrites_esi_fields(self):
        alliance_row = self.structures["alliance"]
        record_report(
            self.pilots["member"],
            ReportDetails(
                system_name="Amamake",
                type_id=35833,
                name="Something else",
                reinforce_hour=4,
            ),
            alliance_row,
            visible_structures(self.pilots["member"]),
        )
        alliance_row.refresh_from_db()
        self.assertEqual(alliance_row.name, "Amamake - alliance")
        self.assertEqual(alliance_row.reinforce_hour, 19)

    def test_ambiguous_hidden_match_is_flagged(self):
        for index in (7, 8):
            EveStructure.objects.create(
                id=2000 + index,
                system_id=TU_O0T,
                system_name="TU-O0T",
                type_id=35825,
                type_name="Raitaru",
                name=f"Hidden {index}",
                corporation=self.corp,
                visibility="private",
            )
        row = record_report(
            self.pilots["sibling_member"],
            ReportDetails(system_name="TU-O0T", type_id=35825),
            None,
            visible_structures(self.pilots["sibling_member"]),
        )
        self.assertTrue(row.possible_duplicate)
        self.assertEqual(row.source, "reported")

    def test_esi_sync_absorbs_reported_row(self):
        timer = EveStructureTimer.objects.create(
            name="Cerulean Cave",
            state="armor",
            type="astrahus",
            timer=timezone.now() + timedelta(hours=5),
            system_name="TU-O0T",
            structure=self.reported,
        )
        esi = EveStructure.objects.create(
            id=1050000000001,
            system_id=TU_O0T,
            system_name="TU-O0T",
            type_id=35832,
            type_name="Astrahus",
            name="TU-O0T - Cerulean Cave",
            reinforce_hour=3,
            corporation=self.corp,
        )
        self.assertEqual(absorb_reported_structure(esi), 1)
        timer.refresh_from_db()
        esi.refresh_from_db()
        self.assertEqual(timer.structure_id, esi.id)
        self.assertEqual(esi.visibility, "alliance")
        self.assertFalse(
            EveStructure.objects.filter(id=self.reported.id).exists()
        )


@patch(ALLOW, return_value=True)
class TimerApiTests(UniverseFixture):
    def test_timers_hide_private_structures(self, _):
        now = timezone.now()
        EveStructureTimer.objects.create(
            name="Private",
            state="armor",
            type="fortizar",
            timer=now + timedelta(hours=2),
            system_name="Amamake",
            structure=self.structures["private"],
        )
        EveStructureTimer.objects.create(
            name="Cerulean Cave",
            state="hull",
            type="astrahus",
            timer=now + timedelta(hours=1),
            system_name="TU-O0T",
        )
        EveStructureTimer.objects.create(
            name="Old",
            state="hull",
            type="astrahus",
            timer=now - timedelta(days=30),
            system_name="TU-O0T",
        )
        response = self.get(self.pilots["member"], "/api/universe/timers")
        names = [row["name"] for row in response.json()["timers"]]
        self.assertEqual(names, ["Cerulean Cave"])
        self.assertTrue(response.json()["timers"][0]["final"])


@patch(ALLOW, return_value=True)
class MoonApiTests(UniverseFixture):
    def setUp(self):
        super().setUp()
        self.moon = EveMoon.objects.create(
            system="Amamake",
            planet="VII",
            moon=1,
            monthly_revenue=3_000_000_000,
        )
        EveMoonDistribution.objects.create(
            moon=self.moon, ore="Xenotime", yield_percent=0.31
        )
        EveMoonScan.objects.create(moon=self.moon, raw_text="Xenotime\t0.31")

    def test_pilot_gets_null_contents(self, _):
        response = self.get(self.pilots["member"], "/api/universe/moons")
        body = response.json()
        self.assertFalse(body["can_view_contents"])
        moon = body["moons"][0]
        self.assertIsNone(moon["monthly_revenue"])
        self.assertIsNone(moon["ores"])
        self.assertIsNone(moon["rarity"])

    def test_structure_manager_sees_contents(self, _):
        response = self.get(self.pilots["director"], "/api/universe/moons")
        moon = response.json()["moons"][0]
        self.assertEqual(moon["rarity"], 64)
        self.assertEqual(moon["monthly_revenue"], 3_000_000_000)
        self.assertEqual(len(moon["scans"]), 1)

    def test_moon_contents_rule(self, _):
        self.assertTrue(can_see_moon_contents(self.pilots["superuser"]))
        self.assertTrue(can_see_moon_contents(self.pilots["steward"]))
        with patch("universe.access.can_use_feature", return_value=False):
            self.assertFalse(can_see_moon_contents(self.pilots["member"]))


class MoonLeakRegressionTests(UniverseFixture):
    """GET /api/moons used to check moons.view twice, so every viewer saw
    every moon's revenue."""

    def test_viewer_without_contents_gets_no_detail(self):
        EveMoon.objects.create(
            system="Amamake",
            planet="VII",
            moon=1,
            monthly_revenue=3_000_000_000,
        )
        with patch("moons.router.can_use_feature", return_value=True), patch(
            "universe.access.can_use_feature", return_value=False
        ):
            response = self.get(self.pilots["member"], "/api/moons")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()[0]["detail"])
