"""Universe: structure visibility, reports, the global timerboard and moons."""

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, Group, User
from django.core.cache import cache
from django.db.models import signals
from django.test import Client
from django.utils import timezone
from eveuniverse.models import EveConstellation, EveRegion, EveSolarSystem

from app.test import TestCase
from app.testing import make_token
from eveonline.constants import MINMATAR_FLEET_ALLIANCE_ID
from eveonline.models import EveAlliance, EveCharacter, EveCorporation
from groups.models import AffiliationType, UserAffiliation
from intel.models import IntelAffiliation, IntelBloc, IntelEntity
from moons.models import (
    EveMoon,
    EveMoonDistribution,
    EveMoonScan,
    MetenoxKill,
)
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
ESI = "eveonline.client.EsiClient"

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

    def test_jump_gate_in_an_unloaded_system_is_found_through_esi(self, _):
        """Most of null-sec is not in the local universe table until
        something loads it; a jump gate there must still be reportable."""
        gate = {
            "system_name": "1DQ1-A",
            "type_id": 35841,
            "name": "1DQ1-A \u00bb 8WA-Z6 - Highway",
        }

        def load(id):  # pylint: disable=redefined-builtin
            return _system(id, "1DQ1-A"), True

        with patch(ESI) as esi, patch(
            "eveuniverse.models.EveSolarSystem.objects.get_or_create_esi",
            side_effect=load,
        ):
            esi.return_value.resolve_universe_ids.return_value.success.return_value = (
                True
            )
            esi.return_value.resolve_universe_ids.return_value.results.return_value = {
                "systems": [{"id": 30004759, "name": "1DQ1-A"}]
            }
            match = self.send(
                self.pilots["member"],
                "post",
                "/api/universe/structures/match",
                gate,
            )
            self.assertTrue(match.json()["system_found"])
            report = self.send(
                self.pilots["member"],
                "post",
                "/api/universe/structures/report",
                gate,
            )
        self.assertEqual(report.status_code, 200, report.content)
        row = EveStructure.objects.get(type_id=35841)
        self.assertEqual((row.system_id, row.name), (30004759, gate["name"]))

    def test_report_takes_the_alliance_from_the_corporation(self, _):
        hostile = EveAlliance.objects.create(
            alliance_id=99010022, name="Scary Wormhole People"
        )
        EveCorporation.objects.create(
            corporation_id=1705300610, name="TDSIN", alliance=hostile
        )
        response = self.send(
            self.pilots["member"],
            "post",
            "/api/universe/structures/report",
            {
                "system_name": "TU-O0T",
                "type_id": 35832,
                "name": "TU-O0T - Hole",
                "corporation_name": "TDSIN",
            },
        )
        self.assertEqual(response.status_code, 200)
        row = EveStructure.objects.get(name="TU-O0T - Hole")
        self.assertEqual(row.owner_alliance_name, "Scary Wormhole People")

    def test_report_asks_esi_for_an_unknown_corporations_alliance(self, _):
        with patch(ESI) as esi:
            client = esi.return_value
            client.resolve_universe_ids.return_value.success.return_value = (
                True
            )
            client.resolve_universe_ids.return_value.results.return_value = {
                "corporations": [{"id": 98000001, "name": "Far Away Corp"}]
            }
            client.get_corporation.return_value.success.return_value = True
            client.get_corporation.return_value.results.return_value = {
                "alliance_id": 99000001
            }
            client.get_alliance.return_value.success.return_value = True
            client.get_alliance.return_value.results.return_value = {
                "name": "Far Away Alliance"
            }
            self.send(
                self.pilots["member"],
                "post",
                "/api/universe/structures/report",
                {
                    "system_name": "TU-O0T",
                    "type_id": 35832,
                    "name": "TU-O0T - Far",
                    "corporation_name": "Far Away Corp",
                },
            )
        row = EveStructure.objects.get(name="TU-O0T - Far")
        self.assertEqual(row.owner_alliance_name, "Far Away Alliance")
        self.assertEqual(row.owner_corporation_name, "Far Away Corp")

    def test_affiliation_comes_from_the_owners_bloc(self, _):
        cache.clear()
        snuffed = IntelEntity.objects.create(
            kind="alliance", eve_id=99004901, name="Snuffed Out"
        )
        bloc = IntelBloc.objects.create(
            name="Snuffed Out", anchor=snuffed, manual=True
        )
        pet = IntelEntity.objects.create(
            kind="alliance", eve_id=99010022, name="Scary Wormhole People"
        )
        IntelAffiliation.objects.create(
            entity=pet,
            bloc=bloc,
            relation="pet",
            status="confirmed",
            confidence=0.9,
        )
        EveAlliance.objects.create(
            alliance_id=99010022, name="Scary Wormhole People"
        )
        self.reported.owner_alliance_name = "Scary Wormhole People"
        self.reported.affiliated_alliance_name = "typed by hand"
        self.reported.save()
        response = self.get(
            self.pilots["member"],
            f"/api/universe/structures/{self.reported.id}",
        )
        self.assertEqual(
            response.json()["affiliated_alliance_name"], "Snuffed Out"
        )

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

    def _moon(self, system, number, ore, revenue):
        moon = EveMoon.objects.create(
            system=system, planet="I", moon=number, monthly_revenue=revenue
        )
        EveMoonDistribution.objects.create(
            moon=moon, ore=ore, yield_percent=0.2
        )
        return moon

    def test_moons_come_a_page_at_a_time(self, _):
        for n in range(1, 6):
            self._moon("Teonusude", n, "Cinnabar", n * 1_000_000)
        url = "/api/universe/moons?page_size=2&page=2"
        body = self.get(self.pilots["director"], url).json()
        self.assertEqual(body["total"], 6)
        self.assertEqual(body["page"], 2)
        self.assertEqual(body["page_size"], 2)
        # Revenue order: Amamake (3b), then Teonusude 5, 4, 3, ...
        self.assertEqual([m["moon"] for m in body["moons"]], [4, 3])

    def test_moons_search_and_rarity_filter(self, _):
        self._moon("Teonusude", 1, "Cinnabar", 1)
        self._moon("Teonusude", 2, "Bitumens", 1)
        director = self.pilots["director"]
        body = self.get(director, "/api/universe/moons?q=teon").json()
        self.assertEqual(body["total"], 2)
        counts = {c["rarity"]: c["count"] for c in body["rarity_counts"]}
        self.assertEqual(counts, {0: 2, 64: 0, 32: 1, 16: 0})
        body = self.get(director, "/api/universe/moons?rarity=64").json()
        self.assertEqual([m["system"] for m in body["moons"]], ["Amamake"])
        body = self.get(director, "/api/universe/moons?q=cinnabar").json()
        self.assertEqual([m["moon"] for m in body["moons"]], [1])

    def test_pilot_cannot_search_or_filter_by_contents(self, _):
        self._moon("Teonusude", 1, "Cinnabar", 1)
        member = self.pilots["member"]
        body = self.get(member, "/api/universe/moons?q=xenotime").json()
        self.assertEqual(body["total"], 0)
        body = self.get(member, "/api/universe/moons?rarity=64").json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["rarity_counts"], [])

    def test_net_orders_and_hides_unprofitable_moons(self, _):
        self.moon.monthly_net = 2_600_000_000
        self.moon.save()
        losing = self._moon("Teonusude", 1, "Bitumens", 300_000_000)
        losing.monthly_net = -65_000_000
        losing.save()
        unpriced = self._moon("Teonusude", 2, "Cinnabar", 900_000_000)
        director = self.pilots["director"]

        body = self.get(director, "/api/universe/moons").json()
        self.assertEqual(
            [m["monthly_net"] for m in body["moons"]],
            [2_600_000_000, -65_000_000, None],
        )
        self.assertEqual(body["unprofitable_hidden"], 0)

        url = "/api/universe/moons?hide_unprofitable=true"
        body = self.get(director, url).json()
        # A moon not priced yet stays: nobody knows it loses ISK.
        self.assertEqual(
            [m["id"] for m in body["moons"]], [self.moon.id, unpriced.id]
        )
        self.assertEqual(body["unprofitable_hidden"], 1)
        counts = {c["rarity"]: c["count"] for c in body["rarity_counts"]}
        self.assertEqual(counts[0], 2)

        body = self.get(director, url + "&rarity=64").json()
        self.assertEqual(body["unprofitable_hidden"], 0)

    def test_pilot_cannot_hide_by_profit(self, _):
        self.moon.monthly_net = -1
        self.moon.save()
        url = "/api/universe/moons?hide_unprofitable=true"
        body = self.get(self.pilots["member"], url).json()
        self.assertEqual(body["total"], 1)
        self.assertIsNone(body["moons"][0]["monthly_net"])
        self.assertIsNone(body["moons"][0]["metenox_kills"])

    def test_profit_lines_and_metenox_kills(self, _):
        self.moon.monthly_net = 1
        self.moon.profit = {
            "output": [
                {"name": "Thulium", "units": 10, "price": 2.5, "isk": 25}
            ],
            "fuel": [
                {"name": "Magmatic Gas", "units": 4, "price": 6.0, "isk": 24}
            ],
            "priced_at": "2026-11-22T10:00:00+00:00",
        }
        self.moon.save()
        now = timezone.now()
        for killmail_id, days in ((1, 90), (2, 12)):
            MetenoxKill.objects.create(
                moon=self.moon,
                killmail_id=killmail_id,
                killmail_hash="h",
                killed_at=now - timedelta(days=days),
                owner_corporation_name=f"Owner {killmail_id}",
                killer_name="Killer",
                attacker_count=34,
            )
        body = self.get(self.pilots["director"], "/api/universe/moons").json()
        moon = body["moons"][0]
        self.assertEqual(moon["profit"]["output"][0]["isk"], 25)
        self.assertEqual(moon["profit"]["fuel"][0]["name"], "Magmatic Gas")
        self.assertEqual(
            [k["killmail_id"] for k in moon["metenox_kills"]], [2, 1]
        )
        self.assertEqual(moon["metenox_kills"][0]["attacker_count"], 34)

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
