"""The battle report: the killmail snapshot, sides, windows, and the API."""

import importlib
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, SimpleTestCase
from django.utils import timezone

from app.test import TestCase
from app.testing import make_token
from feed.helpers.fleet_pilots import invalidate_fleet_pilot_cache
from feed.models import FeedKillmail
from fleets.helpers.fights import battle, rounds
from fleets.helpers.fights import timeline as fights
from fleets.helpers.fights.battle import assign_sides
from fleets.models import (
    EveFleet,
    EveFleetBattleSegment,
    EveFleetFightTimeline,
    EveFleetInstance,
    EveFleetInstanceMember,
)
from fleets.tests import BASE_URL, disconnect_fleet_signals

LANTORN, DAL, AMAMAKE = 30002540, 30002541, 30002537
RIFTER, SLASHER, CAPSULE = 587, 585, 670
US, THEM, THIRD = 99000001, 99000500, 99000800
ALLY_CORP = 98000070


def row(killmail_id, victim, attackers, *, minute=0, ship=RIFTER, isk=100):
    """A snapshot row; victim and attackers are (character, group)."""

    def split(group):
        return (None, group) if group >= 99000000 else (group, None)

    corporation, alliance = split(victim[1])
    return {
        "id": killmail_id,
        "t": f"2026-10-18T18:{minute:02d}:00+00:00",
        "system": LANTORN,
        "ship": ship,
        "isk": isk,
        "pod": False,
        "n": len(attackers),
        "victim": {
            "character": victim[0],
            "corporation": corporation,
            "alliance": alliance,
        },
        "attackers": [
            [character, *split(group), RIFTER, 100, index == 0]
            for index, (character, group) in enumerate(attackers)
        ],
    }


class SideAssignmentTests(SimpleTestCase):
    def two_sides(self):
        return [
            row(1, (10, THEM), [(1, US), (2, US)]),
            row(2, (11, THEM), [(1, US)]),
            row(3, (2, US), [(10, THEM), (11, THEM)]),
        ]

    def test_two_sides(self):
        teams, sides = assign_sides(self.two_sides(), {1, 2})

        self.assertEqual({US: 0, THEM: 1}, teams)
        self.assertEqual("", sides)

    def test_a_group_shooting_both_sides_is_a_third_party(self):
        rows = self.two_sides() + [
            row(4, (12, THEM), [(30, THIRD)]),
            row(5, (3, US), [(30, THIRD), (31, THIRD)]),
        ]

        teams, _ = assign_sides(rows, {1, 2, 3})

        self.assertEqual({US: 0, THEM: 1, THIRD: 2}, teams)

    def test_allies_outside_the_fleet_land_on_our_side(self):
        rows = self.two_sides() + [
            row(4, (12, THEM), [(1, US), (50, ALLY_CORP)]),
            row(5, (13, THEM), [(50, ALLY_CORP)]),
        ]

        teams, _ = assign_sides(rows, {1, 2})

        self.assertEqual(0, teams[ALLY_CORP])
        self.assertEqual(1, teams[THEM])

    def test_their_allies_land_on_their_side(self):
        rows = self.two_sides() + [
            row(4, (1, US), [(10, THEM), (60, 98000060)]),
        ]

        teams, _ = assign_sides(rows, {1, 2})

        self.assertEqual(1, teams[98000060])

    def test_overrides_move_groups_and_ignore_bad_entries(self):
        rows = self.two_sides() + [row(4, (12, THEM), [(30, THIRD)])]

        teams, sides = assign_sides(
            rows,
            {1, 2},
            f"{THIRD}:0, junk,{THEM}:7,123:1,{US}:x,{THIRD}",
        )

        self.assertEqual(0, teams[THIRD])
        self.assertEqual(f"{THIRD}:0", sides)

    def test_the_result_does_not_depend_on_row_order(self):
        rows = self.two_sides() + [
            row(4, (12, THEM), [(30, THIRD)]),
            row(5, (3, US), [(30, THIRD)]),
            row(6, (13, THEM), [(50, ALLY_CORP), (1, US)]),
        ]

        self.assertEqual(
            assign_sides(rows, {1, 2, 3}),
            assign_sides(list(reversed(rows)), {1, 2, 3}),
        )


def member(instance, character_id, joined, last_seen):
    row_ = EveFleetInstanceMember.objects.create(
        eve_fleet_instance=instance,
        character_id=character_id,
        character_name=f"Pilot {character_id}",
        role="squad_member",
        role_name="Squad Member",
        ship_type_id=RIFTER,
        ship_name="Rifter",
        solar_system_id=AMAMAKE,
        solar_system_name="Amamake",
        squad_id=1,
        wing_id=1,
    )
    EveFleetInstanceMember.objects.filter(pk=row_.pk).update(
        join_time=joined, created_at=joined, updated_at=last_seen
    )


def entity(character, group, ship=RIFTER, final=False, damage=500):
    return {
        "character_id": character,
        "corporation_id": group if group < 99000000 else 98000000 + group % 7,
        "alliance_id": group if group >= 99000000 else None,
        "ship_type_id": ship,
        "damage_done": damage,
        "final_blow": final,
    }


def killmail(killmail_id, moment, victim, attackers, *, system=LANTORN):
    """``victim`` and each attacker are (character, group)."""
    victim_entity = entity(*victim)
    return FeedKillmail.objects.create(
        killmail_id=killmail_id,
        hash=f"h{killmail_id}",
        killmail_time=moment,
        solar_system_id=system,
        victim_character_id=victim[0],
        victim_ship_type_id=SLASHER,
        attacker_summary=[
            entity(character, group, final=index == 0)
            for index, (character, group) in enumerate(attackers)
        ]
        + [{"character_id": None, "corporation_id": 1000125}],
        raw_killmail={
            "victim": {
                "character_id": victim[0],
                "corporation_id": victim_entity["corporation_id"],
                "alliance_id": victim_entity["alliance_id"],
            },
            "items": [{"item_type_id": 1}] * 50,
        },
        zkb_meta={"totalValue": 10**7},
    )


def names(ids):
    return {entity_id: f"Name-{entity_id}" for entity_id in ids}


@patch("fleets.helpers.fights.collect.resolve_entity_names", names)
class BattleReportTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        invalidate_fleet_pilot_cache()
        disconnect_fleet_signals()
        self.client = Client()
        self.now = timezone.now()
        self.start = self.now - timedelta(minutes=50)
        self.fleet = EveFleet.objects.create(
            start_time=self.start,
            type="non_strategic",
            status="active",
            created_by=self.user,
        )
        self.instance = EveFleetInstance.objects.create(
            id=1183712315753, eve_fleet=self.fleet
        )
        EveFleetInstance.objects.filter(pk=self.instance.pk).update(
            start_time=self.start, last_updated=self.now
        )
        for pilot in (2001, 2002, 2003):
            member(self.instance, pilot, self.start, self.now)

    def at(self, minutes):
        return self.start + timedelta(minutes=minutes)

    def fight(self):
        """Round 1 in Lantorn with an ally and a third party around it,
        round 2 in Dal."""
        for index in range(5):
            killmail(
                100 + index,
                self.at(10 + index),
                (4000 + index, THEM),
                [(2001, US), (2002, US), (7000, ALLY_CORP)],
            )
        # A third party shooting both sides, inside the padded window.
        killmail(150, self.at(9.2), (4100, THEM), [(8000, THIRD)])
        killmail(151, self.at(14.8), (7100, US), [(8000, THIRD)])
        # Past the window, and in a system round 1 never fought in; both are
        # in the snapshot, which spans the whole fleet.
        killmail(160, self.at(15.5), (4101, THEM), [(8000, THIRD)])
        killmail(161, self.at(12), (4102, THEM), [(8001, THIRD)], system=DAL)
        for index in range(4):
            killmail(
                200 + index,
                self.at(35 + index),
                (2001 + index % 3, US),
                [(6000, THEM), (6001, THEM)],
                system=DAL,
            )

    def report(self, token=None, **query):
        return self.client.get(
            f"{BASE_URL}/{self.fleet.id}/fights/report",
            query,
            HTTP_AUTHORIZATION=f"Bearer {token or self.token}",
        )

    def window(self, start, end, **query):
        """The report from minute ``start`` to minute ``end``."""
        return self.report(
            start=self.at(start).isoformat(),
            end=self.at(end).isoformat(),
            **query,
        )

    def team(self, body, index):
        return next(t for t in body["teams"] if t["index"] == index)

    def test_rebuild_snapshots_every_mail_around_the_rounds(self):
        self.fight()

        timeline = fights.rebuild(self.fleet, now=self.now)

        self.assertEqual(
            {100, 101, 102, 103, 104, 150, 151, 160, 161, 200, 201, 202, 203},
            {r["id"] for r in timeline.battle_killmails},
        )
        self.assertIsNotNone(timeline.battle_collected_at)
        first = next(r for r in timeline.battle_killmails if r["id"] == 100)
        self.assertEqual(4, first["n"])
        self.assertEqual(3, len(first["attackers"]))
        self.assertEqual(THEM, first["victim"]["alliance"])
        self.assertEqual(
            "Name-7000", timeline.battle_names["characters"]["7000"]
        )
        self.assertEqual(
            "Name-99000800", timeline.battle_names["groups"][str(THIRD)]
        )

    def test_groups_show_their_bloc_to_intel_viewers(self):
        # pylint: disable=import-outside-toplevel
        from django.contrib.auth.models import Permission

        from intel.models import IntelAffiliation, IntelBloc, IntelEntity

        main = IntelEntity.objects.create(kind="alliance", eve_id=99000999)
        bloc = IntelBloc.objects.create(name="Snuffed Out", anchor=main)
        IntelAffiliation.objects.create(
            entity=IntelEntity.objects.create(kind="alliance", eve_id=THEM),
            bloc=bloc,
            relation="pet",
            status="suggested",
        )
        self.fight()
        fights.rebuild(self.fleet, now=self.now)

        theirs = self.team(self.report().json(), 1)
        self.assertIsNone(theirs["groups"][0]["bloc"])

        self.user.user_permissions.add(
            Permission.objects.get(codename="view_intelreport")
        )
        theirs = self.team(self.report().json(), 1)
        self.assertEqual(
            {"id": bloc.id, "name": "Snuffed Out", "likely": True},
            theirs["groups"][0]["bloc"],
        )

    def test_a_window_has_every_system_in_it_and_its_sides(self):
        self.fight()
        fights.rebuild(self.fleet, now=self.now)

        response = self.window(9, 15)

        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertFalse(body["whole"])
        self.assertEqual([LANTORN, DAL], [s["id"] for s in body["systems"]])
        self.assertEqual(
            self.at(9).isoformat()[:19], body["window_start"][:19]
        )
        self.assertEqual(self.at(15).isoformat()[:19], body["window_end"][:19])
        self.assertEqual(self.at(9.2).isoformat()[:19], body["start"][:19])
        self.assertEqual(6, body["minutes"])
        self.assertTrue(body["complete"])
        self.assertEqual(
            [150, 100, 101, 102, 161, 103, 104, 151],
            [k["id"] for k in body["killmails"]],
        )

        ours, theirs, third = (self.team(body, i) for i in (0, 1, 2))
        self.assertTrue(ours["ours"])
        self.assertEqual({US, ALLY_CORP}, {g["id"] for g in ours["groups"]})
        self.assertEqual([THEM], [g["id"] for g in theirs["groups"]])
        self.assertEqual([THIRD], [g["id"] for g in third["groups"]])
        self.assertEqual("alliance", third["groups"][0]["kind"])
        self.assertEqual("Name-99000800", third["groups"][0]["name"])

        self.assertEqual(4, ours["totals"]["pilots"])
        self.assertEqual(1, ours["totals"]["ships_lost"])
        self.assertEqual(5 * 10**7, ours["totals"]["isk_destroyed"])
        self.assertEqual(83, ours["totals"]["efficiency"])
        self.assertEqual(7, theirs["totals"]["ships_lost"])
        self.assertEqual(2, third["totals"]["pilots"])
        self.assertEqual(3 * 10**7, third["totals"]["isk_destroyed"])

        pilot = next(p for p in ours["pilots"] if p["character_id"] == 2001)
        self.assertEqual("Name-2001", pilot["name"])
        self.assertEqual(5, pilot["kills"])
        self.assertEqual(2500, pilot["damage"])
        self.assertEqual(
            [
                {
                    "type_id": RIFTER,
                    "name": "Type 587",
                    "lost": False,
                    "killmail_id": None,
                }
            ],
            pilot["ships"],
        )
        victim = next(p for p in theirs["pilots"] if p["character_id"] == 4000)
        self.assertEqual(
            [(SLASHER, True, 100)],
            [
                (s["type_id"], s["lost"], s["killmail_id"])
                for s in victim["ships"]
            ],
        )

        mail = next(k for k in body["killmails"] if k["id"] == 100)
        self.assertEqual(1, mail["team"])
        self.assertEqual(4, mail["attackers"])
        self.assertEqual(2001, mail["final_blow"]["character_id"])
        self.assertEqual(THEM, mail["victim_group_id"])

    def test_sides_query_moves_a_group(self):
        self.fight()
        fights.rebuild(self.fleet, now=self.now)

        body = self.window(9, 15, sides=f"{THIRD}:1,bogus").json()

        self.assertEqual(f"{THIRD}:1", body["sides"])
        self.assertIn(THIRD, [g["id"] for g in self.team(body, 1)["groups"]])
        self.assertEqual([0, 1], [t["index"] for t in body["teams"]])

    def test_an_old_timeline_is_backfilled_from_the_feed(self):
        self.fight()
        fights.rebuild(self.fleet, now=self.now)
        EveFleetFightTimeline.objects.update(
            battle_killmails=[], battle_names={}, battle_collected_at=None
        )

        body = self.report().json()

        self.assertTrue(body["complete"])
        self.assertEqual(13, len(body["killmails"]))
        timeline = EveFleetFightTimeline.objects.get()
        self.assertIsNotNone(timeline.battle_collected_at)
        self.assertEqual(13, len(timeline.battle_killmails))

    def test_purged_mails_fall_back_to_our_own_and_say_so(self):
        self.fight()
        fights.rebuild(self.fleet, now=self.now)
        EveFleetFightTimeline.objects.update(
            battle_killmails=[], battle_names={}, battle_collected_at=None
        )
        FeedKillmail.objects.all().delete()

        body = self.window(9, 15).json()

        self.assertFalse(body["complete"])
        self.assertEqual(
            [100, 101, 102, 103, 104], [k["id"] for k in body["killmails"]]
        )
        ours = self.team(body, 0)
        self.assertEqual(
            {2001, 2002}, {p["character_id"] for p in ours["pilots"]}
        )
        self.assertEqual(5, self.team(body, 1)["totals"]["ships_lost"])

        losses = self.window(34, 40).json()
        self.assertFalse(losses["complete"])
        self.assertEqual(4, self.team(losses, 0)["totals"]["ships_lost"])
        self.assertEqual(
            {6000, 6001},
            {p["character_id"] for p in self.team(losses, 1)["pilots"]},
        )

    def test_unknown_fleet_timeline_or_segment_is_404(self):
        self.assertEqual(404, self.report().status_code)
        self.fight()
        fights.rebuild(self.fleet, now=self.now)

        self.assertEqual(200, self.report().status_code)
        self.assertEqual(404, self.report(segment=987).status_code)
        missing = self.client.get(
            f"{BASE_URL}/987654/fights/report",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(404, missing.status_code)

    def test_the_whole_fleet_is_every_mail_with_its_activity(self):
        self.fight()
        fights.rebuild(self.fleet, now=self.now)

        body = self.report().json()

        self.assertTrue(body["whole"])
        self.assertEqual(13, len(body["killmails"]))
        self.assertEqual([LANTORN, DAL], [s["id"] for s in body["systems"]])
        self.assertEqual(
            self.at(8.2).isoformat()[:19], body["span_start"][:19]
        )
        self.assertEqual(
            13 * 10**7, sum(sum(m["isk"]) for m in body["activity"])
        )
        # Our four losses in Dal close the night, a minute apart.
        self.assertEqual(
            [[10**7, 0, 0]] * 4, [m["isk"] for m in body["activity"][-4:]]
        )
        self.assertEqual(2, len(body["fights"]))
        self.assertEqual(
            self.at(9).isoformat()[:19], body["fights"][0]["start"][:19]
        )
        self.assertEqual([], body["segments"])
        self.assertTrue(body["can_edit_segments"])

    def test_sides_come_from_the_window_alone(self):
        self.fight()
        fights.rebuild(self.fleet, now=self.now)

        dal = self.window(34, 40).json()

        self.assertEqual([0, 1], [t["index"] for t in dal["teams"]])
        self.assertEqual(
            [THEM], [g["id"] for g in self.team(dal, 1)["groups"]]
        )
        self.assertEqual(4, self.team(dal, 0)["totals"]["ships_lost"])

    def test_the_fc_saves_and_deletes_a_segment(self):
        self.fight()
        fights.rebuild(self.fleet, now=self.now)
        url = f"{BASE_URL}/{self.fleet.id}/fights/segments"

        saved = self.client.post(
            url,
            {
                "name": "  Lantorn   brawl ",
                "start": self.at(9).isoformat(),
                "end": self.at(15).isoformat(),
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, saved.status_code)
        segment = saved.json()
        self.assertEqual("Lantorn brawl", segment["name"])
        body = self.report(segment=segment["id"]).json()
        self.assertEqual(segment["id"], body["segment_id"])
        self.assertEqual(
            [(segment["id"], "Lantorn brawl")],
            [(s["id"], s["name"]) for s in body["segments"]],
        )
        self.assertEqual(8, len(body["killmails"]))

        deleted = self.client.delete(
            f"{url}/{segment['id']}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(204, deleted.status_code)
        self.assertFalse(EveFleetBattleSegment.objects.exists())
        self.assertEqual(
            404,
            self.client.delete(
                f"{url}/{segment['id']}",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            ).status_code,
        )

    def test_a_blank_name_is_the_window_times(self):
        self.fight()
        fights.rebuild(self.fleet, now=self.now)

        saved = self.client.post(
            f"{BASE_URL}/{self.fleet.id}/fights/segments",
            {
                "start": self.at(15).isoformat(),
                "end": self.at(9).isoformat(),
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        ).json()

        self.assertEqual(
            f"{self.at(9):%H:%M}–{self.at(15):%H:%M} ET", saved["name"]
        )
        self.assertLess(saved["start"], saved["end"])

    def test_only_the_fc_edits_segments(self):
        self.fight()
        fights.rebuild(self.fleet, now=self.now)
        segment = EveFleetBattleSegment.objects.create(
            eve_fleet=self.fleet,
            name="Mine",
            start=self.at(9),
            end=self.at(15),
        )
        other = make_token(User.objects.create(username="other-fc"))
        url = f"{BASE_URL}/{self.fleet.id}/fights/segments"

        created = self.client.post(
            url,
            {"start": self.at(9).isoformat(), "end": self.at(15).isoformat()},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {other}",
        )
        deleted = self.client.delete(
            f"{url}/{segment.id}", HTTP_AUTHORIZATION=f"Bearer {other}"
        )

        self.assertEqual(403, created.status_code)
        self.assertEqual(403, deleted.status_code)
        self.assertEqual(1, EveFleetBattleSegment.objects.count())

    def test_while_live_a_stranger_cannot_see_the_report(self):
        self.fight()
        fights.rebuild(self.fleet, now=self.now)
        stranger = User.objects.create(username="stranger")
        endpoint = importlib.import_module(
            "fleets.endpoints.fleet.get_fleet_fight_report"
        )

        self.assertEqual(
            403, self.report(token=make_token(stranger)).status_code
        )
        with patch.object(endpoint, "_fleet_authorized", return_value=True):
            self.assertEqual(
                403, self.report(token=make_token(stranger)).status_code
            )

    def test_fights_payload_links_the_whole_fleet(self):
        self.fight()
        fights.rebuild(self.fleet, now=self.now)

        body = self.client.get(
            f"{BASE_URL}/{self.fleet.id}/fights",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        ).json()

        links = body["links"]
        self.assertIn(f"/related/{LANTORN}/", links["zkillboard"])
        self.assertIn(str(DAL), links["zkillboard"])
        hour = self.at(10).strftime("%Y%m%d%H")
        self.assertTrue(
            links["brtools"].endswith(f"/{LANTORN}/{hour}00"),
            links["brtools"],
        )
        self.assertIsNone(links["evekill"])


class GroupKindTests(SimpleTestCase):
    """Old alliances have ids below 99,000,000; the mails say which is which."""

    OLD_ALLIANCE = 1988009451
    OLD_CORP = 1026712316

    def _mail(self):
        mail = row(1, (10, 98000001), [(20, 99000002)])
        mail["victim"]["alliance"] = self.OLD_ALLIANCE
        mail["attackers"].append([21, self.OLD_CORP, None, RIFTER, 50, False])
        return mail

    def test_an_old_alliance_on_the_mails_is_an_alliance(self):
        alliances = battle.alliance_ids([self._mail()])
        self.assertEqual(
            "alliance", battle.group_kind(self.OLD_ALLIANCE, alliances)
        )
        self.assertEqual(
            "corporation", battle.group_kind(self.OLD_CORP, alliances)
        )

    def test_hostiles_take_their_kind_from_the_timeline_names(self):
        timeline_names = {"alliances": [self.OLD_ALLIANCE]}
        self.assertEqual(
            "alliance", rounds.group_kind(self.OLD_ALLIANCE, timeline_names)
        )
        self.assertEqual(
            "corporation", rounds.group_kind(99000002, timeline_names)
        )
        # Payloads from before the list existed fall back to the id range.
        self.assertEqual("alliance", rounds.group_kind(99000002, {}))
