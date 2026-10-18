"""The fleet fight timeline: rounds, edits, events, ingest, the API."""

import importlib
import json
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, SimpleTestCase
from django.utils import timezone

from app.test import TestCase
from app.testing import make_token
from eveonline.models import EveCharacter
from feed.helpers.fleet_pilots import invalidate_fleet_pilot_cache
from feed.helpers.ingest import upsert_feed_killmail_from_r2z2
from feed.models import FeedKillmail, FeedMonitoredSystem, FeedR2z2Cursor
from feed.tests.helpers import make_killmail_payload
from fleets.helpers.fights import timeline as fights
from fleets.helpers.fights.collect import collect_events
from fleets.helpers.fights.rounds import (
    build_payload,
    zkill_related_url,
)
from fleets.models import (
    EveFleet,
    EveFleetFightEdit,
    EveFleetFightTimeline,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetInstanceMemberShipSnapshot,
)
from fleets.tests import BASE_URL, disconnect_fleet_signals

FIXTURE = Path(__file__).parent / "fixtures" / "fight_timeline_fleet_2405.json"
LANTORN, DAL, AMAMAKE, JITA = 30002540, 30002541, 30002537, 30000142
UTC = dt_timezone.utc
START = datetime(2026, 10, 18, 16, 55, tzinfo=UTC)
END = datetime(2026, 10, 18, 19, 22, tzinfo=UTC)


def fleet_2405_rows() -> list[dict]:
    """The real killmails of fleet 2405, a night of four rounds."""
    data = json.loads(FIXTURE.read_text())
    return [
        {
            "id": killmail_id,
            "t": f"{moment}+00:00",
            "outcome": "kill" if outcome == "k" else "loss",
            "system": system,
            "ship": ship,
            "victim": None,
            "victim_group": None,
            "isk": isk,
            "pending": False,
            "pod": bool(pod),
            "pilots": [],
            "hostiles": [],
        }
        for killmail_id, moment, outcome, system, ship, isk, pod in data[
            "rows"
        ]
    ]


def cut(rows, edits=(), events=()):
    return build_payload(
        rows,
        events=list(events),
        names={"our_groups": [99011978]},
        edits=list(edits),
        battles={},
        start=START,
        end=END,
        now=END,
    )


def shape(payload):
    return [
        (
            r["kind"],
            r["start"][11:16],
            r["end"][11:16],
            r["ships_destroyed"],
            r["ships_lost"],
        )
        for r in payload["rounds"]
    ]


class RoundCuttingTests(SimpleTestCase):
    def test_fleet_2405_is_four_rounds_and_three_skirmishes(self):
        payload = cut(fleet_2405_rows())

        self.assertEqual(
            [
                ("round", "17:17", "17:29", 24, 6),
                ("skirmish", "17:37", "17:40", 0, 3),
                ("round", "17:46", "18:01", 14, 24),
                ("skirmish", "18:09", "18:09", 0, 1),
                ("skirmish", "18:18", "18:20", 0, 3),
                ("round", "18:27", "18:48", 31, 32),
                ("round", "18:54", "19:02", 3, 15),
            ],
            shape(payload),
        )
        self.assertEqual(4, payload["round_count"])
        self.assertEqual(3, payload["skirmish_count"])
        self.assertEqual(
            [1, None, 2, None, None, 3, 4],
            [r["number"] for r in payload["rounds"]],
        )
        self.assertEqual(
            [87, 34, 56, 8],
            [
                r["efficiency"]
                for r in payload["rounds"]
                if r["kind"] == "round"
            ],
        )
        self.assertEqual(72, payload["totals"]["ships_destroyed"])
        self.assertEqual(84, payload["totals"]["ships_lost"])

    def test_round_three_spans_both_systems(self):
        round_three = cut(fleet_2405_rows())["rounds"][5]

        self.assertEqual(
            [LANTORN, DAL], [s["id"] for s in round_three["systems"]]
        )
        options = json.loads(
            unquote(round_three["links"]["zkillboard"].split("/o/")[1][:-1])
        )
        self.assertEqual([LANTORN, DAL], options["systems"])
        self.assertEqual([99011978], options["A"])
        self.assertTrue(
            round_three["links"]["brtools"].endswith("/30002540/202610181800")
        )

    def test_merge_pulls_a_skirmish_into_the_next_round(self):
        rows = fleet_2405_rows()
        edit = {
            "id": 1,
            "kind": "merge",
            "start": "2026-10-18T18:18:18+00:00",
            "end": "2026-10-18T18:48:47+00:00",
        }

        payload = cut(rows, edits=[edit])

        merged = payload["rounds"][4]
        self.assertEqual(
            ("round", "18:18", "18:48", 31, 35), shape(payload)[4]
        )
        self.assertEqual([1], merged["merge_edit_ids"])
        self.assertEqual(6, len(payload["rounds"]))

    def test_a_late_mail_inside_a_merge_stays_merged(self):
        rows = fleet_2405_rows()
        late = dict(rows[0], id=1, t="2026-10-18T18:23:00+00:00")
        rows = sorted(rows + [late], key=lambda r: (r["t"], r["id"]))
        edit = {
            "id": 1,
            "kind": "merge",
            "start": "2026-10-18T18:18:18+00:00",
            "end": "2026-10-18T18:48:47+00:00",
        }

        payload = cut(rows, edits=[edit])

        self.assertEqual(("round", "18:18", "18:48"), shape(payload)[4][:3])

    def test_split_at_a_gap_starts_a_new_round(self):
        split = {
            "id": 2,
            "kind": "split",
            "start": "2026-10-18T18:44:47+00:00",
            "end": None,
        }

        payload = cut(fleet_2405_rows(), edits=[split])

        self.assertEqual(
            [
                ("round", "18:27", "18:42", 31, 27),
                ("round", "18:44", "18:48", 0, 5),
            ],
            shape(payload)[5:7],
        )
        self.assertEqual([2], payload["rounds"][6]["split_edit_ids"])

    def test_split_gaps_offer_the_lull_inside_a_round(self):
        round_three = cut(fleet_2405_rows())["rounds"][5]

        self.assertIn(
            "2026-10-18T18:44:47+00:00",
            [gap["at"] for gap in round_three["split_gaps"]],
        )

    def test_reship_in_a_lull_starts_a_new_round(self):
        rows = [
            dict(r, t=t)
            for r, t in zip(
                fleet_2405_rows()[:8],
                [
                    f"2026-10-18T18:{m:02d}:00+00:00"
                    for m in (0, 1, 2, 3, 6, 7, 8, 9)
                ],
            )
        ]
        reship = {"kind": "reship", "at": "2026-10-18T18:04:30+00:00"}

        payload = cut(rows, events=[reship])

        self.assertEqual(
            ["18:00", "18:06"], [r["start"][11:16] for r in payload["rounds"]]
        )

    def test_live_round_is_fighting_while_mails_are_recent(self):
        rows = fleet_2405_rows()[:20]
        last = datetime.fromisoformat(rows[-1]["t"])

        payload = build_payload(
            rows,
            events=[],
            names={},
            edits=[],
            battles={},
            start=START,
            end=None,
            now=last + timedelta(minutes=2),
        )

        self.assertTrue(payload["live"])
        self.assertTrue(payload["rounds"][-1]["fighting"])

    def test_zkill_link_widens_for_a_long_round(self):
        url = zkill_related_url(
            [LANTORN],
            datetime(2026, 10, 18, 18, 10, tzinfo=UTC),
            datetime(2026, 10, 18, 21, 30, tzinfo=UTC),
            [],
        )

        self.assertIn("/related/30002540/202610181800/o/", url)
        self.assertIn("hoursAfter", unquote(url))

    def test_chart_bins_cover_the_fleet(self):
        chart = cut(fleet_2405_rows())["chart"]

        self.assertEqual(1, chart["bin_minutes"])
        self.assertEqual(147, len(chart["bins"]))
        self.assertEqual(72, sum(k for k, _ in chart["bins"]))


def member(instance, character_id, joined, last_seen, ship=587):
    row = EveFleetInstanceMember.objects.create(
        eve_fleet_instance=instance,
        character_id=character_id,
        character_name=f"Pilot {character_id}",
        role="squad_member",
        role_name="Squad Member",
        ship_type_id=ship,
        ship_name="Rifter",
        solar_system_id=AMAMAKE,
        solar_system_name="Amamake",
        squad_id=1,
        wing_id=1,
    )
    EveFleetInstanceMember.objects.filter(pk=row.pk).update(
        join_time=joined, created_at=joined, updated_at=last_seen
    )
    return row


def killmail(killmail_id, moment, *, victim, attackers, system=LANTORN):
    return FeedKillmail.objects.create(
        killmail_id=killmail_id,
        hash=f"h{killmail_id}",
        killmail_time=moment,
        solar_system_id=system,
        victim_character_id=victim,
        victim_ship_type_id=587,
        attacker_summary=[
            {"character_id": a, "alliance_id": 99000001 + (a % 2)}
            for a in attackers
        ],
        raw_killmail={"victim": {"alliance_id": 99000500}},
        zkb_meta={"totalValue": 10**8},
    )


@patch("fleets.helpers.fights.collect.resolve_entity_names", lambda ids: {})
class FightTimelineTestCase(TestCase):
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
        self.instance.refresh_from_db()
        for pilot in (2001, 2002, 2003):
            member(self.instance, pilot, self.start, self.now)

    def at(self, minutes):
        return self.start + timedelta(minutes=minutes)

    def fight(self):
        """Two fights 20 minutes apart: a win, then a loss."""
        for index in range(5):
            killmail(
                100 + index,
                self.at(10 + index),
                victim=4000 + index,
                attackers=[2001, 2002, 5000 + index],
            )
        for index in range(4):
            killmail(
                200 + index,
                self.at(35 + index),
                victim=2001 + index % 3,
                attackers=[6000, 6001],
            )

    def get(self, token=None):
        return self.client.get(
            f"{BASE_URL}/{self.fleet.id}/fights",
            HTTP_AUTHORIZATION=f"Bearer {token or self.token}",
        )

    def test_rebuild_cuts_two_rounds_and_records_both_sides(self):
        self.fight()

        timeline = fights.rebuild(self.fleet, now=self.now)

        rounds = timeline.payload["rounds"]
        self.assertEqual(["round", "round"], [r["kind"] for r in rounds])
        self.assertEqual(
            (5, 0), (rounds[0]["ships_destroyed"], rounds[0]["ships_lost"])
        )
        self.assertEqual(
            (0, 4), (rounds[1]["ships_destroyed"], rounds[1]["ships_lost"])
        )
        self.assertEqual(2, rounds[0]["our_pilots"])
        self.assertEqual(2, rounds[1]["hostile_pilots"])
        self.assertTrue(timeline.payload["live"])
        self.assertIn(99000001, timeline.names["our_groups"])

    def test_api_serves_the_fc_and_lets_them_merge_and_reset(self):
        self.fight()
        fights.rebuild(self.fleet, now=self.now)

        response = self.get()
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("live", body["status"])
        self.assertTrue(body["can_edit"])
        self.assertEqual(2, body["round_count"])

        merged = self.client.post(
            f"{BASE_URL}/{self.fleet.id}/fights/merge",
            {
                "start": body["rounds"][0]["start"],
                "end": body["rounds"][1]["end"],
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        ).json()
        self.assertEqual(1, merged["round_count"])
        self.assertEqual(1, len(merged["edits"]))

        reset = self.client.delete(
            f"{BASE_URL}/{self.fleet.id}/fights/edits",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        ).json()
        self.assertEqual(2, reset["round_count"])
        self.assertFalse(EveFleetFightEdit.objects.exists())

    def test_split_and_undo_one_edit(self):
        self.fight()
        fights.rebuild(self.fleet, now=self.now)
        first_kill = FeedKillmail.objects.get(killmail_id=103).killmail_time

        split = self.client.post(
            f"{BASE_URL}/{self.fleet.id}/fights/split",
            {"at": first_kill.isoformat()},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        ).json()
        self.assertEqual(3, len(split["rounds"]))
        edit_id = split["edits"][0]["id"]

        undone = self.client.delete(
            f"{BASE_URL}/{self.fleet.id}/fights/edits/{edit_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        ).json()
        self.assertEqual(2, len(undone["rounds"]))

    def test_while_live_a_stranger_cannot_see_the_fights(self):
        self.fight()
        fights.rebuild(self.fleet, now=self.now)
        stranger = User.objects.create(username="stranger")

        endpoint = importlib.import_module(
            "fleets.endpoints.fleet.get_fleet_fights"
        )
        with patch.object(endpoint, "_fleet_authorized", return_value=True):
            self.assertEqual(403, self.get(make_token(stranger)).status_code)
            EveCharacter.objects.create(
                character_id=2002, character_name="Pilot 2002", user=stranger
            )
            self.assertEqual(200, self.get(make_token(stranger)).status_code)

    def test_editing_needs_a_fleet_manager(self):
        self.fight()
        fights.rebuild(self.fleet, now=self.now)
        stranger = User.objects.create(username="stranger")

        response = self.client.delete(
            f"{BASE_URL}/{self.fleet.id}/fights/edits",
            HTTP_AUTHORIZATION=f"Bearer {make_token(stranger)}",
        )
        self.assertEqual(403, response.status_code)

    def test_first_read_queues_a_build(self):
        with patch("fleets.tasks.rebuild_fight_timeline.delay") as delay:
            body = self.get().json()

        self.assertEqual("building", body["status"])
        delay.assert_called_once_with(self.fleet.id)

    def test_feed_behind_shows_on_a_live_fleet(self):
        self.fight()
        fights.rebuild(self.fleet, now=self.now)
        FeedR2z2Cursor.objects.create(
            pk=1, last_request_at=timezone.now() - timedelta(minutes=10)
        )

        self.assertIsNotNone(self.get().json()["feed_behind_since"])

    def test_due_fleets_skip_settled_and_standing(self):
        self.assertEqual([self.fleet.id], fights.due_fleet_ids(self.now))
        EveFleetFightTimeline.objects.create(
            eve_fleet=self.fleet, settled_at=self.now
        )
        self.assertEqual([], fights.due_fleet_ids(self.now))

    def test_reship_wave_becomes_an_event(self):
        members = list(EveFleetInstanceMember.objects.all())
        for row in members:
            for ship, minutes in ((587, 1), (17732, 30)):
                snapshot = EveFleetInstanceMemberShipSnapshot.objects.create(
                    member=row,
                    ship_type_id=ship,
                    ship_name=(
                        "Rifter" if ship == 587 else "Tempest Fleet Issue"
                    ),
                    solar_system_id=AMAMAKE,
                    solar_system_name="Amamake",
                )
                EveFleetInstanceMemberShipSnapshot.objects.filter(
                    pk=snapshot.pk
                ).update(created_at=self.at(minutes))
        with patch("fleets.helpers.fights.collect.RESHIP_WAVE_MIN", 3):
            events = collect_events([self.instance])

        reship = [e for e in events if e["kind"] == "reship"]
        self.assertEqual(1, len(reship))
        self.assertEqual(
            [{"name": "Tempest Fleet Issue", "count": 3}], reship[0]["ships"]
        )

    def test_sweep_adds_a_missed_mail_and_reprices_an_esi_one(self):
        self.fight()
        timeline = fights.rebuild(self.fleet, now=self.now)
        FeedKillmail.objects.filter(killmail_id=100).update(
            zkb_meta={"hash": "h100"}
        )
        missed = make_killmail_payload(
            300,
            solar_system_id=JITA,
            killmail_time=self.at(12),
            attacker_id_base=2001,
            attacker_count=1,
        )["killmail"]
        entries = [
            {"killmail_id": 100, "zkb": {"hash": "h100", "totalValue": 5}},
            {**missed, "zkb": {"hash": "h300", "totalValue": 7}},
        ]

        class Response:
            status_code = 200

            def __init__(self, data):
                self.data = data

            def raise_for_status(self):
                return None

            def json(self):
                return self.data

        pages = iter([Response(entries)] + [Response([])] * 5)
        with patch(
            "fleets.helpers.fights.timeline.zkill_get",
            lambda url: next(pages),
        ), patch("fleets.helpers.fights.timeline.time.sleep"):
            stats = fights.sweep(self.fleet, now=self.now)

        self.assertEqual(1, stats["added"])
        self.assertEqual(1, stats["repriced"])
        self.assertTrue(FeedKillmail.objects.filter(killmail_id=300).exists())
        timeline.refresh_from_db()
        self.assertIsNotNone(timeline.swept_at)


class FleetPilotIngestTests(TestCase):
    def setUp(self):
        super().setUp()
        invalidate_fleet_pilot_cache()
        disconnect_fleet_signals()
        FeedMonitoredSystem.objects.create(solar_system_id=AMAMAKE)
        fleet = EveFleet.objects.create(
            start_time=timezone.now(),
            type="non_strategic",
            created_by=self.user,
        )
        instance = EveFleetInstance.objects.create(id=77, eve_fleet=fleet)
        member(instance, 2001, timezone.now(), timezone.now())

    def tearDown(self):
        invalidate_fleet_pilot_cache()

    def test_mail_outside_the_warzone_is_kept_when_a_fleet_pilot_is_on_it(
        self,
    ):
        ours = make_killmail_payload(
            1, solar_system_id=JITA, attacker_id_base=2001, attacker_count=2
        )
        theirs = make_killmail_payload(
            2, solar_system_id=JITA, attacker_id_base=9000, attacker_count=2
        )

        self.assertIsNotNone(upsert_feed_killmail_from_r2z2(ours))
        self.assertIsNone(upsert_feed_killmail_from_r2z2(theirs))
