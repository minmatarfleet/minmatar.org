"""Finished-fleet Participants tab: hulls flown, reships, roles, no-shows."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from eveuniverse.models import EveCategory, EveGroup, EveType

from app.test import TestCase
from app.testing import make_token
from eveonline.models import EveCharacter, EvePlayer
from fittings.models import EveDoctrine, EveDoctrineFitting, EveFitting
from fleets.helpers.doctrine_flown import doctrine_hulls, pick_doctrine
from fleets.helpers.opsec import sensitive_hull_ids
from fleets.models import (
    EveFleetFightTimeline,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetInstanceMemberShipSnapshot,
    EveFleetRoleVolunteer,
    EveFleetShipVolunteer,
)
from fleets.test_fleet_roles import DAMNATION_EFT, DEVOTER_EFT, GUARDIAN_EFT
from fleets.tests import (
    BASE_URL,
    disconnect_fleet_signals,
    make_test_fleet,
    setup_fleet_reference_data,
)
from users.helpers import add_user_permission

CAPSULE = (670, "Capsule")
TYPHOON = (644, "Typhoon")
GUARDIAN = (11987, "Guardian")
DAMNATION = (22474, "Damnation")
DEVOTER = (12017, "Devoter")
ZARMAZD = (49712, "Zarmazd")
EXEQUROR = (634, "Exequror")
MAELSTROM = (24690, "Maelstrom")
NAGLFAR = (19722, "Naglfar")
RAPIER = (11963, "Rapier")
SIN = (22430, "Sin")

HULL_GROUPS = {
    CAPSULE: (29, "Capsule"),
    TYPHOON: (27, "Battleship"),
    GUARDIAN: (832, "Logistics"),
    ZARMAZD: (832, "Logistics"),
    DAMNATION: (540, "Command Ship"),
    DEVOTER: (894, "Heavy Interdiction Cruiser"),
    EXEQUROR: (26, "Cruiser"),
    MAELSTROM: (27, "Battleship"),
    NAGLFAR: (485, "Dreadnought"),
    RAPIER: (833, "Force Recon Ship"),
    SIN: (898, "Black Ops"),
}

OWN = 1001  # the regular viewer's character


def _seed_hulls():
    category, _ = EveCategory.objects.get_or_create(
        id=6, defaults={"name": "Ship", "published": True}
    )
    for (type_id, name), (group_id, group_name) in HULL_GROUPS.items():
        group, _ = EveGroup.objects.get_or_create(
            id=group_id,
            defaults={
                "name": group_name,
                "published": True,
                "eve_category": category,
            },
        )
        EveType.objects.get_or_create(
            id=type_id,
            defaults={
                "name": name,
                "published": True,
                "eve_group": group,
                "enabled_sections": EveType.enabled_sections.dogmas,
            },
        )


def _strategic_fc(username="strategic"):
    user = User.objects.create(username=username)
    add_user_permission(user, "view_evefleet")
    add_user_permission(user, "manage_any_fleet")
    return user


class FleetParticipantsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        _seed_hulls()
        add_user_permission(self.user, "view_evefleet")
        EveCharacter.objects.create(
            character_id=OWN, character_name="Own Pilot", user=self.user
        )
        self.doctrine = EveDoctrine.objects.create(
            name="Armor", type="non_strategic", description=""
        )
        self.fits = {
            hull: self._doctrine_fit(name, hull[0], eft)
            for hull, name, eft in (
                (DAMNATION, "[FL33T] Damnation", DAMNATION_EFT),
                (GUARDIAN, "[FL33T] Guardian", GUARDIAN_EFT),
                (DEVOTER, "Devoter", DEVOTER_EFT),
            )
        }
        self.fc_user = User.objects.create(username="fc")
        self.sfc = _strategic_fc()
        self.fleet = make_test_fleet("Fleet", self.fc_user)
        self.fleet.doctrine = self.doctrine
        self.fleet.save()
        self.instance = EveFleetInstance.objects.create(
            id=7001, eve_fleet=self.fleet
        )
        EveFleetInstance.objects.filter(pk=self.instance.pk).update(
            end_time=timezone.now()
        )
        self.clock = timezone.now() - timedelta(hours=2)

        # Typhoon for most of the fleet, podded, back in a Guardian: logi
        # from a later hull.
        self._pilot(
            OWN,
            "Own Pilot",
            [TYPHOON, CAPSULE, GUARDIAN],
            GUARDIAN,
            at=[0, 90, 91],
        )
        # Typhoon, podded and stayed in the pod.
        self._pilot(3002, "Podded", [TYPHOON, CAPSULE], CAPSULE)
        # Joined in a pod, then boarded the links ship.
        self._pilot(3003, "Booster", [CAPSULE, DAMNATION], DAMNATION)
        # No snapshots at all: the member row is the only ship.
        self._pilot(3004, "Cyno Alt", [], DEVOTER)
        # Only ever a capsule.
        self._pilot(3005, "Pod Only", [CAPSULE], CAPSULE)
        # Off-doctrine logi hull: logi from its group.
        self._pilot(3006, "Trig", [ZARMAZD], ZARMAZD)
        # Off-doctrine cruiser: not logi without a fit.
        self._pilot(3007, "Exeq", [EXEQUROR], EXEQUROR)

    def _doctrine_fit(self, name, ship_id, eft):
        fitting = EveFitting.objects.create(
            name=name, ship_id=ship_id, description="", eft_format=eft
        )
        EveDoctrineFitting.objects.create(
            doctrine=self.doctrine, fitting=fitting, role="support"
        )
        return fitting

    def _pilot(
        self, character_id, name, snapshots, final, instance=None, at=None
    ):
        """``at`` gives each snapshot's minute from the start of the clock;
        without it snapshots follow each other a minute apart."""
        start = timezone.now() - timedelta(hours=2)
        member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance or self.instance,
            character_id=character_id,
            character_name=name,
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=final[0],
            ship_name=final[1],
            solar_system_id=30002537,
            solar_system_name="Amamake",
            squad_id=1,
            wing_id=1,
        )
        for index, (ship_type_id, ship_name) in enumerate(snapshots):
            snapshot = EveFleetInstanceMemberShipSnapshot.objects.create(
                member=member,
                ship_type_id=ship_type_id,
                ship_name=ship_name,
                solar_system_id=30002537,
                solar_system_name="Amamake",
            )
            if at is None:
                self.clock += timedelta(minutes=1)
                moment = self.clock
            else:
                moment = start + timedelta(minutes=at[index])
            EveFleetInstanceMemberShipSnapshot.objects.filter(
                pk=snapshot.pk
            ).update(created_at=moment)
        return member

    def _get(self, user=None, path="participants"):
        token = make_token(user) if user else self.token
        return self.client.get(
            f"{BASE_URL}/{self.fleet.id}/{path}",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def _body(self, user=None):
        response = self._get(user)
        self.assertEqual(200, response.status_code, response.content)
        return response.json()

    @staticmethod
    def _role(body, role):
        return next(row for row in body["roles_flown"] if row["role"] == role)

    def test_each_pilot_counts_once_by_the_hull_flown_longest(self):
        body = self._body(self.sfc)

        self.assertEqual(7, body["pilots"])
        self.assertEqual(
            [
                ("Typhoon", 2),
                ("Capsule", 1),
                ("Damnation", 1),
                ("Devoter", 1),
                ("Exequror", 1),
                ("Zarmazd", 1),
            ],
            [(row["ship_name"], row["count"]) for row in body["flew"]],
        )
        self.assertEqual(644, body["flew"][0]["ship_type_id"])

    def test_changed_ship_and_ended_in_pod(self):
        body = self._body()

        # Own Pilot (3 hulls), Podded and Booster (2 each).
        self.assertEqual(3, body["changed_ship"])
        # Podded and Pod Only.
        self.assertEqual(2, body["ended_in_pod"])

    def test_a_pilot_in_two_instances_is_one_pilot(self):
        later = EveFleetInstance.objects.create(id=7002, eve_fleet=self.fleet)
        EveFleetInstance.objects.filter(pk=later.pk).update(
            start_time=timezone.now() + timedelta(hours=1)
        )
        # Podded reships into a Typhoon in the second instance.
        self._pilot(3002, "Podded", [TYPHOON], TYPHOON, instance=later)

        body = self._body(self.sfc)
        self.assertEqual(7, body["pilots"])
        self.assertEqual(
            ("Typhoon", 2),
            (
                body["flew"][0]["ship_name"],
                body["flew"][0]["count"],
            ),
        )
        self.assertEqual(1, body["ended_in_pod"])

    def test_roles_come_from_any_hull_flown(self):
        body = self._body(self.sfc)

        logi = self._role(body, "logi")
        self.assertEqual("Logistics", logi["label"])
        self.assertEqual(2, logi["count"])
        self.assertEqual(
            [("Own Pilot", "Guardian"), ("Trig", "Zarmazd")],
            [(p["character_name"], p["ship_name"]) for p in logi["pilots"]],
        )
        self.assertEqual(
            [
                {"ship_name": "Guardian", "count": 1},
                {"ship_name": "Zarmazd", "count": 1},
            ],
            logi["hulls"],
        )
        links = self._role(body, "links")
        self.assertEqual(
            [(3003, "Damnation")],
            [(p["character_id"], p["ship_name"]) for p in links["pilots"]],
        )
        self.assertEqual(
            [{"ship_name": "Damnation", "count": 1}], links["hulls"]
        )
        cyno = self._role(body, "cyno")
        self.assertEqual(
            ["Cyno Alt"], [p["character_name"] for p in cyno["pilots"]]
        )

    def test_hidden_roster_names_only_your_own_pilots(self):
        self.fleet.hide_volunteers = True
        self.fleet.save()

        logi = self._role(self._body(), "logi")
        self.assertEqual(2, logi["count"])
        self.assertEqual([OWN], [p["character_id"] for p in logi["pilots"]])

    def test_logi_fc_volunteers(self):
        EveFleetRoleVolunteer.objects.create(
            eve_fleet=self.fleet,
            character_id=3006,
            character_name="Trig",
            role=EveFleetRoleVolunteer.ROLE_LOGI_ANCHOR,
        )
        body = self._body()
        self.assertEqual(
            ["Trig"], [v["character_name"] for v in body["logi_fc"]]
        )

    def _sign_up(self, character_id, name, hull):
        EveFleetShipVolunteer.objects.create(
            eve_fleet=self.fleet,
            character_id=character_id,
            character_name=name,
            fitting=self.fits[hull],
        )

    def test_no_shows_for_the_fc(self):
        self._sign_up(OWN, "Own Pilot", GUARDIAN)
        self._sign_up(9001, "Never Came", DEVOTER)

        body = self._body(self.fc_user)
        self.assertEqual(
            [
                {
                    "character_id": 9001,
                    "character_name": "Never Came",
                    "ship_name": "Devoter",
                    "ship_type_id": 12017,
                }
            ],
            body["no_shows"],
        )
        self.assertEqual(2, body["signed_up"])
        # Cyno Alt flew a cyno hull: hidden from an FC who is not a
        # Strategic FC, so not counted either.
        self.assertEqual(5, body["joined_without_signing_up"])

    def test_no_shows_hidden_from_a_regular_pilot(self):
        self._sign_up(9001, "Never Came", DEVOTER)

        body = self._body()
        self.assertIsNone(body["no_shows"])
        self.assertIsNone(body["signed_up"])
        self.assertIsNone(body["joined_without_signing_up"])

    def test_viewer_who_cannot_see_the_fleet(self):
        outsider = User.objects.create(username="outsider")

        expected = self._get(outsider, "roles").status_code
        self.assertEqual(403, expected)
        self.assertEqual(expected, self._get(outsider).status_code)

    def test_pilots_per_hull(self):
        typhoon = self._body()["flew"][0]

        self.assertEqual("Typhoon", typhoon["ship_name"])
        self.assertEqual(
            [
                {
                    "character_id": OWN,
                    "character_name": "Own Pilot",
                    "kills": None,
                    "losses": None,
                },
                {
                    "character_id": 3002,
                    "character_name": "Podded",
                    "kills": None,
                    "losses": None,
                },
            ],
            typhoon["pilots"],
        )

    def test_hidden_roster_names_only_your_own_pilots_per_hull(self):
        self.fleet.hide_volunteers = True
        self.fleet.save()

        typhoon = self._body()["flew"][0]
        self.assertEqual(2, typhoon["count"])
        self.assertEqual([OWN], [p["character_id"] for p in typhoon["pilots"]])
        # A Strategic FC still sees everyone.
        typhoon = self._body(self.sfc)["flew"][0]
        self.assertEqual(2, len(typhoon["pilots"]))

    def test_opsec_leaves_out_cyno_pilots_for_a_regular_viewer(self):
        EveFleetRoleVolunteer.objects.create(
            eve_fleet=self.fleet,
            character_id=3004,
            character_name="Cyno Alt",
            role=EveFleetRoleVolunteer.ROLE_LOGI_ANCHOR,
        )
        body = self._body()

        self.assertTrue(body["opsec_filtered"])
        self.assertEqual(6, body["pilots"])
        self.assertNotIn("Devoter", [row["ship_name"] for row in body["flew"]])
        self.assertEqual(
            ["logi", "links"], [row["role"] for row in body["roles_flown"]]
        )
        self.assertEqual([], body["logi_fc"])

        body = self._body(self.sfc)
        self.assertFalse(body["opsec_filtered"])
        self.assertEqual(7, body["pilots"])
        self.assertEqual(
            ["Cyno Alt"], [v["character_name"] for v in body["logi_fc"]]
        )

    def test_no_timeline_no_engagements_or_doctrine(self):
        body = self._body()

        self.assertEqual([], body["engagements"])
        self.assertIsNone(body["engagement"])
        self.assertEqual([], body["doctrine_flown"])
        response = self.client.get(
            f"{BASE_URL}/{self.fleet.id}/participants?engagement=1",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(404, response.status_code)

    def test_timeline_without_rounds_is_one_whole_fleet_segment(self):
        start = timezone.now() - timedelta(hours=1)
        EveFleetFightTimeline.objects.create(
            eve_fleet=self.fleet,
            payload={
                "rounds": [
                    {
                        "kind": "skirmish",
                        "number": None,
                        "start": start.isoformat(),
                        "end": start.isoformat(),
                    }
                ]
            },
        )
        body = self._body()

        self.assertEqual([], body["engagements"])
        [segment] = body["doctrine_flown"]
        self.assertEqual([], segment["positions"])
        # Typhoon x2, Damnation, Exequror, Zarmazd: one Armor hull in five.
        self.assertIsNone(segment["doctrine_id"])
        self.assertEqual(0, segment["share"])
        self.assertEqual(5, segment["pilots"])
        self.assertEqual(
            ("Typhoon", 2),
            (segment["hulls"][0]["ship_name"], segment["hulls"][0]["count"]),
        )
        self.assertIsNotNone(segment["start"])

    def test_unknown_fleet(self):
        response = self.client.get(
            f"{BASE_URL}/999999/participants",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(404, response.status_code)


class SensitiveHullsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        _seed_hulls()

    def test_capitals_covert_hulls_and_cyno_fits(self):
        doctrine = EveDoctrine.objects.create(
            name="Armor", type="non_strategic", description=""
        )
        fitting = EveFitting.objects.create(
            name="Devoter",
            ship_id=DEVOTER[0],
            description="",
            eft_format=DEVOTER_EFT,
        )
        EveDoctrineFitting.objects.create(
            doctrine=doctrine, fitting=fitting, role="support"
        )
        fleet = make_test_fleet("Fleet", self.user)
        fleet.doctrine = doctrine
        fleet.save()

        hulls = {h[0] for h in (TYPHOON, NAGLFAR, RAPIER, SIN, DEVOTER)}
        self.assertEqual(
            {NAGLFAR[0], RAPIER[0], SIN[0], DEVOTER[0]},
            sensitive_hull_ids(fleet, hulls),
        )


class DoctrinePickTestCase(TestCase):
    def test_needs_half_the_pilots_and_prefers_the_planned_doctrine(self):
        doctrines = {
            1: {"name": "Typhoons", "hulls": {TYPHOON[0]}},
            2: {"name": "Armor", "hulls": {TYPHOON[0], GUARDIAN[0]}},
        }
        hulls = {1: TYPHOON, 2: TYPHOON, 3: EXEQUROR, 4: EXEQUROR}
        # Tie on two Typhoons: the planned doctrine wins, else by name.
        self.assertEqual(2, pick_doctrine(hulls, doctrines))
        self.assertEqual(1, pick_doctrine(hulls, doctrines, 1))
        hulls[5] = EXEQUROR
        self.assertIsNone(pick_doctrine(hulls, doctrines))

    def test_doctrine_hulls_in_one_query(self):
        doctrine = EveDoctrine.objects.create(
            name="Armor", type="non_strategic", description=""
        )
        for ship_id in (DAMNATION[0], GUARDIAN[0]):
            EveDoctrineFitting.objects.create(
                doctrine=doctrine,
                fitting=EveFitting.objects.create(
                    name=f"Fit {ship_id}",
                    ship_id=ship_id,
                    description="",
                    eft_format="",
                ),
                role="primary",
            )
        with self.assertNumQueries(1):
            found = doctrine_hulls()
        self.assertEqual(
            {doctrine.id: {"name": "Armor", "hulls": {22474, 11987}}}, found
        )


class TimelineFleetFixture(TestCase):
    """A fleet with a fight timeline, and pilots joining and reshipping.

    Round 1 (position 1) is a Typhoon fight; a skirmish sits at position 2;
    rounds 2 and 3 (positions 3, 4) are fought in Maelstroms.
    """

    def setUp(self):
        super().setUp()
        self.client = Client()
        disconnect_fleet_signals()
        setup_fleet_reference_data()
        _seed_hulls()
        add_user_permission(self.user, "view_evefleet")
        EveCharacter.objects.create(
            character_id=OWN, character_name="Own Pilot", user=self.user
        )
        self.sfc = _strategic_fc()
        armor = EveDoctrine.objects.create(
            name="Armor", type="non_strategic", description=""
        )
        self.typhoons = EveDoctrine.objects.create(
            name="Typhoons", type="non_strategic", description=""
        )
        self.maelstroms = EveDoctrine.objects.create(
            name="Maelstroms", type="non_strategic", description=""
        )
        for doctrine, hull, eft in (
            (armor, DEVOTER, DEVOTER_EFT),
            (armor, GUARDIAN, GUARDIAN_EFT),
            (self.typhoons, TYPHOON, "[Typhoon, Typhoon]\n"),
            (self.maelstroms, MAELSTROM, "[Maelstrom, Maelstrom]\n"),
        ):
            EveDoctrineFitting.objects.create(
                doctrine=doctrine,
                fitting=EveFitting.objects.create(
                    name=f"{doctrine.name} {hull[1]}",
                    ship_id=hull[0],
                    description="",
                    eft_format=eft,
                ),
                role="primary",
            )
        self.fleet = make_test_fleet(
            "Fleet", User.objects.create(username="fc")
        )
        self.fleet.doctrine = armor
        self.fleet.save()
        self.instance = EveFleetInstance.objects.create(
            id=7101, eve_fleet=self.fleet
        )
        self.t0 = timezone.now() - timedelta(hours=3)
        EveFleetInstance.objects.filter(pk=self.instance.pk).update(
            start_time=self.t0, end_time=self.t0 + timedelta(minutes=80)
        )

        self._pilot(
            OWN,
            "Own Pilot",
            0,
            80,
            [(1, TYPHOON), (15, CAPSULE), (35, MAELSTROM)],
        )
        self._pilot(3002, "Typhoon Two", 0, 80, [(2, TYPHOON)])
        self._pilot(3003, "Late Maelstrom", 38, 80, [(38, MAELSTROM)])
        self._pilot(3004, "Early Leaver", 0, 25, [(3, TYPHOON)])
        self._pilot(3005, "Second Maelstrom", 36, 80, [(36, MAELSTROM)])
        self._pilot(3006, "Dread", 0, 80, [(4, NAGLFAR)])
        self._pilot(3007, "Recon", 0, 80, [(5, RAPIER)])
        self._pilot(3008, "Cyno", 0, 80, [(6, DEVOTER)])

        EveFleetFightTimeline.objects.create(
            eve_fleet=self.fleet,
            payload={
                "rounds": [
                    self._round("round", 1, 10, 20),
                    self._round("skirmish", None, 30, 31),
                    self._round("round", 2, 40, 50),
                    self._round("round", 3, 60, 70),
                ]
            },
        )

    def _at(self, minutes):
        return self.t0 + timedelta(minutes=minutes)

    def _round(self, kind, number, start, end):
        return {
            "kind": kind,
            "number": number,
            "start": self._at(start).isoformat(),
            "end": self._at(end).isoformat(),
        }

    def _pilot(self, character_id, name, joined, last_seen, ships):
        final = ships[-1][1]
        member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=self.instance,
            character_id=character_id,
            character_name=name,
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=final[0],
            ship_name=final[1],
            solar_system_id=30002537,
            solar_system_name="Amamake",
            squad_id=1,
            wing_id=1,
        )
        EveFleetInstanceMember.objects.filter(pk=member.pk).update(
            join_time=self._at(joined),
            created_at=self._at(joined),
            updated_at=self._at(last_seen),
        )
        for minutes, (ship_type_id, ship_name) in ships:
            snapshot = EveFleetInstanceMemberShipSnapshot.objects.create(
                member=member,
                ship_type_id=ship_type_id,
                ship_name=ship_name,
                solar_system_id=30002537,
                solar_system_name="Amamake",
            )
            EveFleetInstanceMemberShipSnapshot.objects.filter(
                pk=snapshot.pk
            ).update(created_at=self._at(minutes))

    def _get(self, user=None, query=""):
        token = make_token(user) if user else self.token
        return self.client.get(
            f"{BASE_URL}/{self.fleet.id}/participants{query}",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def _body(self, user=None, query=""):
        response = self._get(user, query)
        self.assertEqual(200, response.status_code, response.content)
        return response.json()

    @staticmethod
    def _flew(body):
        return [(row["ship_name"], row["count"]) for row in body["flew"]]


class FleetEngagementsTestCase(TimelineFleetFixture):
    """Rounds of the fight timeline narrow the tab; doctrine per round."""

    def test_engagements_list_only_rounds(self):
        body = self._body()

        self.assertEqual(
            [(1, 1), (3, 2), (4, 3)],
            [(e["position"], e["number"]) for e in body["engagements"]],
        )
        self.assertIsNone(body["engagement"])

    def test_engagement_counts_pilots_present_by_their_hull_then(self):
        body = self._body(query="?engagement=1")

        self.assertEqual(1, body["engagement"])
        # The late Maelstroms were not there yet; Own Pilot counts by the
        # Typhoon they lost in the round.
        self.assertEqual(3, body["pilots"])
        self.assertEqual([("Typhoon", 3)], self._flew(body))
        self.assertEqual(
            ["Early Leaver", "Own Pilot", "Typhoon Two"],
            [p["character_name"] for p in body["flew"][0]["pilots"]],
        )
        self.assertEqual(1, body["changed_ship"])
        self.assertEqual(1, body["ended_in_pod"])

        body = self._body(query="?engagement=3")
        # The early leaver is gone; Own Pilot is back in a Maelstrom.
        self.assertEqual(4, body["pilots"])
        self.assertEqual([("Maelstrom", 3), ("Typhoon", 1)], self._flew(body))
        self.assertEqual(0, body["ended_in_pod"])

    def test_missing_engagement_is_not_found(self):
        self.assertEqual(404, self._get(query="?engagement=9").status_code)

    def test_a_skirmish_can_be_picked(self):
        body = self._body(query="?engagement=2")

        self.assertEqual("skirmish", body["fight"]["kind"])
        self.assertIsNone(body["fight"]["number"])
        # Own Pilot sat in a pod, counted by the Typhoon they lost; the
        # early leaver is inside the last-seen grace; no Maelstroms yet.
        self.assertEqual([("Typhoon", 3)], self._flew(body))
        self.assertEqual([], body["roster"])
        self.assertEqual([], body["phases"])

    def test_opsec_hides_capital_recon_and_cyno_pilots(self):
        body = self._body()

        self.assertTrue(body["opsec_filtered"])
        self.assertEqual(5, body["pilots"])
        flown = {row["ship_name"] for row in body["flew"]}
        self.assertFalse(flown & {"Naglfar", "Rapier", "Devoter"})
        self.assertNotIn("cyno", [r["role"] for r in body["roles_flown"]])
        self.assertEqual(3, self._body(query="?engagement=1")["pilots"])

    def test_strategic_fc_sees_everyone(self):
        body = self._body(self.sfc)

        self.assertFalse(body["opsec_filtered"])
        self.assertEqual(8, body["pilots"])
        flown = {row["ship_name"] for row in body["flew"]}
        self.assertTrue({"Naglfar", "Rapier", "Devoter"} <= flown)
        cyno = next(r for r in body["roles_flown"] if r["role"] == "cyno")
        self.assertEqual(
            ["Cyno"], [p["character_name"] for p in cyno["pilots"]]
        )
        self.assertEqual(6, self._body(self.sfc, "?engagement=1")["pilots"])

    def test_doctrine_flown_per_round_merging_neighbours(self):
        segments = self._body()["doctrine_flown"]

        self.assertEqual(
            [
                ([1], "Typhoons", 100, 3),
                ([3, 4], "Maelstroms", 75, 4),
            ],
            [
                (
                    s["positions"],
                    s["doctrine_name"],
                    s["share"],
                    s["pilots"],
                )
                for s in segments
            ],
        )
        self.assertEqual(self.typhoons.id, segments[0]["doctrine_id"])
        for key, minutes in (("start", 40), ("end", 70)):
            self.assertAlmostEqual(
                self._at(minutes),
                parse_datetime(segments[1][key]),
                delta=timedelta(seconds=1),
            )
        self.assertEqual(
            [
                {"ship_type_id": 24690, "ship_name": "Maelstrom", "count": 3},
                {"ship_type_id": 644, "ship_name": "Typhoon", "count": 1},
            ],
            segments[1]["hulls"],
        )

    def test_doctrine_flown_for_a_strategic_fc_counts_hidden_hulls(self):
        first = self._body(self.sfc)["doctrine_flown"][0]

        # Three Typhoons of six pilots is still half.
        self.assertEqual(
            ("Typhoons", 50, 6),
            (first["doctrine_name"], first["share"], first["pilots"]),
        )

    def test_doctrine_flown_queries_do_not_grow_with_rounds(self):
        with self.assertNumQueries(self._queries()):
            self._get()
        timeline = EveFleetFightTimeline.objects.get(eve_fleet=self.fleet)
        timeline.payload["rounds"] += [
            self._round("round", n, 70 + n, 71 + n) for n in range(4, 12)
        ]
        timeline.save()
        with self.assertNumQueries(self._queries()):
            self._get()

    def _queries(self):
        with CaptureQueriesContext(connection) as ctx:
            self._get()
        return len(ctx.captured_queries)


class FleetRosterTestCase(TimelineFleetFixture):
    """People in join order, kills from the timeline, in-fleet and parts.

    Typhoon Two is an alt on the viewer's account and its primary.
    """

    def setUp(self):
        super().setUp()
        EveCharacter.objects.create(
            character_id=3002, character_name="Typhoon Two", user=self.user
        )
        EvePlayer.objects.create(
            nickname="viewer",
            user=self.user,
            primary_character=EveCharacter.objects.get(character_id=3002),
        )
        timeline = EveFleetFightTimeline.objects.get(eve_fleet=self.fleet)
        timeline.killmails = [
            self._mail(12, "kill", pilots=[OWN, 3002]),
            self._mail(14, "loss", victim=OWN),
            self._mail(15, "loss", victim=OWN, pod=True),
            self._mail(45, "kill", pilots=[3003]),
        ]
        timeline.payload["events"] = [
            {"kind": "reship", "at": self._at(3).isoformat(), "count": 3},
            {"kind": "reship", "at": self._at(37).isoformat(), "count": 3},
        ]
        timeline.save()

    def _mail(self, minutes, outcome, pilots=(), victim=None, pod=False):
        return {
            "t": self._at(minutes).isoformat(),
            "outcome": outcome,
            "pilots": list(pilots),
            "victim": victim,
            "pod": pod,
        }

    def test_whole_fleet_counts_the_hull_flown_longest(self):
        body = self._body()

        # Own Pilot flew the Typhoon 14 minutes and the Maelstrom 45.
        self.assertEqual([("Maelstrom", 3), ("Typhoon", 2)], self._flew(body))

    def test_fights_list_rounds_and_skirmishes(self):
        body = self._body()

        self.assertEqual(
            [
                (1, "round", 1),
                (2, "skirmish", None),
                (3, "round", 2),
                (4, "round", 3),
            ],
            [(f["position"], f["kind"], f["number"]) for f in body["fights"]],
        )

    def test_roster_folds_alts_into_one_person_in_join_order(self):
        body = self._body()

        self.assertEqual(5, body["characters"])
        self.assertEqual(4, body["people"])
        self.assertEqual(
            [
                ("Early Leaver", False, ["Early Leaver"]),
                ("Typhoon Two", True, ["Typhoon Two", "Own Pilot"]),
                ("Second Maelstrom", False, ["Second Maelstrom"]),
                ("Late Maelstrom", False, ["Late Maelstrom"]),
            ],
            [
                (
                    person["character_name"],
                    person["registered"],
                    [c["character_name"] for c in person["characters"]],
                )
                for person in body["roster"]
            ],
        )
        own = body["roster"][1]["characters"][1]
        self.assertEqual(
            ["Typhoon", "Capsule", "Maelstrom"],
            [ship["ship_name"] for ship in own["ships"]],
        )
        self.assertEqual("Maelstrom", own["ship_name"])

    def test_kills_and_losses_from_the_timeline(self):
        body = self._body()

        person = body["roster"][1]
        self.assertEqual((2, 1), (person["kills"], person["losses"]))
        own = person["characters"][1]
        self.assertEqual((1, 1), (own["kills"], own["losses"]))
        self.assertAlmostEqual(
            self._at(14),
            parse_datetime(own["lost_at"][0]),
            delta=timedelta(seconds=1),
        )
        # Own Pilot, Typhoon Two and Late Maelstrom; two of them one person.
        self.assertEqual(3, body["on_killmail"])
        self.assertEqual(2, body["people_on_killmail"])

        engagement = self._body(query="?engagement=1")
        typhoons = engagement["flew"][0]["pilots"]
        self.assertEqual(
            [
                ("Early Leaver", 0, 0),
                ("Own Pilot", 1, 1),
                ("Typhoon Two", 1, 0),
            ],
            [(p["character_name"], p["kills"], p["losses"]) for p in typhoons],
        )
        self.assertEqual(2, engagement["on_killmail"])
        self.assertEqual(1, engagement["people_on_killmail"])

    def test_no_timeline_means_unknown_kills(self):
        EveFleetFightTimeline.objects.filter(eve_fleet=self.fleet).delete()

        body = self._body()
        self.assertIsNone(body["roster"][0]["kills"])
        self.assertIsNone(body["on_killmail"])
        self.assertEqual([], body["fights"])
        self.assertEqual(1, len(body["phases"]))

    def test_in_fleet_series_and_peak(self):
        body = self._body()

        self.assertEqual(4, body["peak"])
        self.assertAlmostEqual(
            self._at(38),
            parse_datetime(body["peak_at"]),
            delta=timedelta(minutes=1),
        )
        counts = [point["count"] for point in body["in_fleet"]]
        self.assertEqual(3, counts[0])
        self.assertEqual(0, counts[-1])

    def test_parts_split_at_reships_after_the_form_up(self):
        phases = self._body()["phases"]

        # The minute-3 reship is the form-up; minute 37 splits the fleet.
        self.assertEqual(2, len(phases))
        self.assertEqual(
            [[("Typhoon", 3)], [("Maelstrom", 3), ("Typhoon", 1)]],
            [
                [(h["ship_name"], h["count"]) for h in phase["hulls"]]
                for phase in phases
            ],
        )
        self.assertEqual([3, 4], [phase["peak"] for phase in phases])

    def test_hidden_roster_names_only_your_own_people(self):
        self.fleet.hide_volunteers = True
        self.fleet.save()

        body = self._body()
        self.assertEqual(
            ["Typhoon Two"],
            [person["character_name"] for person in body["roster"]],
        )
        self.assertEqual(3, body["hidden_pilots"])
        self.assertEqual(4, body["people"])

    def test_opsec_leaves_hidden_hulls_out_of_the_roster(self):
        names = {
            c["character_name"]
            for person in self._body()["roster"]
            for c in person["characters"]
        }
        self.assertFalse(names & {"Dread", "Recon", "Cyno"})
        everyone = {
            c["character_name"]
            for person in self._body(self.sfc)["roster"]
            for c in person["characters"]
        }
        self.assertTrue({"Dread", "Recon", "Cyno"} <= everyone)
