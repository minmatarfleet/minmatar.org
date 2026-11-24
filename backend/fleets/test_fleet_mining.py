"""Mining fleet tracking: stints, readings, close-out and results."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from unittest.mock import MagicMock

import factory
from django.db.models import signals
from django.test import override_settings
from django.utils import timezone
from eveuniverse.models import EveType

from alliance.helpers.landing_pulse import UNDISCLOSED
from alliance.tests.test_landing_pulse import _system
from buyback.tests.helpers import ensure_type
from eveonline.helpers.characters.mining import (
    mining_ledger_read,
    mining_totals_since,
    sync_character_mining,
)
from eveonline.models import EveCharacter
from eveonline.models.characters import (
    EveCharacterMiningDelta,
    EveCharacterMiningEntry,
)
from fleets.helpers import mining
from fleets.helpers.member_ships import (
    apply_esi_fleet_member,
    mark_members_left,
)
from fleets.models import (
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetMiningSegment as Segment,
    close_fleet_mining,
)
from fleets.test_group_fleets import (  # pylint: disable=unused-import
    GroupFleetTestBase,
    setUpModule,
    tearDownModule,
)

VELD = 1230
SCORDITE = 1228
PILOT_A = 95000001
PILOT_B = 95000002
SYSTEM = 30002068  # Amamake, low sec
HIGH_SYSTEM = 30002510  # Rens, high sec
SHIP = 32880


def esi_member(character_id):
    return {
        "character_id": character_id,
        "join_time": timezone.now(),
        "role": "squad_member",
        "role_name": "Squad Member",
        "ship_type_id": SHIP,
        "solar_system_id": SYSTEM,
        "squad_id": 1,
        "station_id": None,
        "takes_fleet_warp": True,
        "wing_id": 1,
    }


RESOLVED = {
    PILOT_A: "Miner A",
    PILOT_B: "Miner B",
    SHIP: "Venture",
    SYSTEM: "Amamake",
}


class MiningTestBase(GroupFleetTestBase):
    def setUp(self):
        super().setUp()
        self.fleet = self.group_fleet(track_mining=True)
        self.instance = EveFleetInstance.objects.create(
            id=1001, eve_fleet=self.fleet
        )
        with factory.django.mute_signals(signals.post_save, signals.pre_save):
            for character_id in (PILOT_A, PILOT_B):
                EveCharacter.objects.create(
                    character_id=character_id,
                    character_name=RESOLVED[character_id],
                )
        for type_id, name, group_id in (
            (VELD, "Veldspar", 462),
            (SCORDITE, "Scordite", 460),
        ):
            eve_type = ensure_type(
                type_id=type_id,
                name=name,
                group_id=group_id,
                group_name=name,
                category_id=25,
                category_name="Asteroid",
            )
            EveType.objects.filter(pk=eve_type.pk).update(volume=0.1)
        # Every reading returns what self.ledger says for that pilot.
        self.ledger = {PILOT_A: {}, PILOT_B: {}}
        self.esi_down = False
        patches = [
            patch.object(mining, "has_mining_scope", return_value=True),
            patch.object(mining, "_read", side_effect=self.fake_read),
            patch.object(mining, "_queue"),
            patch.object(
                mining,
                "get_history_averages_by_type_id",
                return_value={VELD: Decimal("10"), SCORDITE: Decimal("20")},
            ),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def fake_read(self, segment):
        if self.esi_down:
            return None
        return dict(self.ledger[segment.member.character_id])

    def poll(self, *present):
        """One member poll listing these pilots."""
        for character_id in present:
            apply_esi_fleet_member(
                self.instance, esi_member(character_id), RESOLVED
            )
        mark_members_left(self.instance, set(present))

    def segments(self, character_id):
        return list(
            Segment.objects.filter(member__character_id=character_id).order_by(
                "id"
            )
        )

    def read_all(self, kind):
        take = {
            "start": mining.take_start_reading,
            "poll": mining.take_poll_reading,
            "end": mining.take_end_reading,
        }[kind]
        for segment in Segment.objects.all():
            take(segment.id)

    def results(self, name_pilot=lambda cid, name: (cid, name)):
        return mining.fleet_mining_results(self.fleet, name_pilot)


class StintTests(MiningTestBase):
    def test_join_poll_leave_gives_the_delta(self):
        self.ledger[PILOT_A] = {str(VELD): 1000}
        self.poll(PILOT_A)
        self.read_all("start")
        [segment] = self.segments(PILOT_A)
        self.assertEqual(segment.status, Segment.STATUS_OPEN)
        self.assertEqual(segment.since_date, timezone.now().date())

        self.ledger[PILOT_A] = {str(VELD): 1600, str(SCORDITE): 50}
        self.read_all("poll")
        pilot = self.results()["pilots"][0]
        self.assertEqual(pilot["status"], "measuring")
        self.assertEqual(
            {o["type_id"]: o["quantity"] for o in pilot["ores"]},
            {VELD: 600, SCORDITE: 50},
        )

        self.ledger[PILOT_A] = {str(VELD): 2000, str(SCORDITE): 50}
        self.poll()  # pilot A is gone
        segment.refresh_from_db()
        self.assertEqual(segment.status, Segment.STATUS_CLOSING)
        self.assertIsNotNone(
            EveFleetInstanceMember.objects.get(character_id=PILOT_A).left_at
        )
        self.read_all("end")

        result = self.results()
        pilot = result["pilots"][0]
        self.assertEqual(pilot["status"], "done")
        self.assertEqual(pilot["ores"][0]["quantity"], 1000)
        self.assertEqual(pilot["ores"][0]["volume_m3"], 100.0)
        self.assertEqual(pilot["isk_estimate"], 1000 * 10 + 50 * 20)
        self.assertFalse(result["measuring"])
        self.assertEqual(result["volume_m3"], 105.0)

    def test_rejoin_opens_a_new_stint_and_both_add_up(self):
        self.ledger[PILOT_A] = {str(VELD): 0}
        self.poll(PILOT_A)
        self.read_all("start")
        self.ledger[PILOT_A] = {str(VELD): 300}
        self.poll()
        self.read_all("end")

        # Solo mining between stints must not count.
        self.ledger[PILOT_A] = {str(VELD): 900}
        self.poll(PILOT_A)
        self.read_all("start")
        self.ledger[PILOT_A] = {str(VELD): 1000}
        self.poll()
        self.read_all("end")

        self.assertEqual(len(self.segments(PILOT_A)), 2)
        member = EveFleetInstanceMember.objects.get(character_id=PILOT_A)
        self.assertIsNotNone(member.left_at)
        quantity = self.results()["pilots"][0]["ores"][0]["quantity"]
        self.assertEqual(quantity, 300 + 100)

    def test_staying_in_fleet_keeps_one_stint(self):
        self.poll(PILOT_A)
        self.poll(PILOT_A)
        self.poll(PILOT_A)
        self.assertEqual(len(self.segments(PILOT_A)), 1)

    def test_pilot_without_scope_is_listed_and_never_read(self):
        with patch.object(mining, "has_mining_scope", return_value=False):
            self.poll(PILOT_A)
            self.poll(PILOT_A)
        [segment] = self.segments(PILOT_A)
        self.assertEqual(segment.status, Segment.STATUS_NO_SCOPE)
        result = self.results()
        self.assertEqual(result["pilots"][0]["status"], "no_scope")
        self.assertEqual(result["pilots_no_scope"], 1)

    def test_pilot_not_on_the_site_is_no_scope(self):
        apply_esi_fleet_member(
            self.instance,
            esi_member(PILOT_B) | {"character_id": 96000000},
            RESOLVED | {96000000: "Stranger"},
        )
        [segment] = self.segments(96000000)
        self.assertEqual(segment.status, Segment.STATUS_NO_SCOPE)

    def test_fleet_end_closes_every_stint(self):
        self.poll(PILOT_A, PILOT_B)
        self.read_all("start")
        close_fleet_mining(self.fleet)
        statuses = set(Segment.objects.values_list("status", flat=True))
        self.assertEqual(statuses, {Segment.STATUS_CLOSING})
        self.assertTrue(self.results()["measuring"])

    def test_end_reading_esi_down_closes_on_the_last_poll(self):
        self.ledger[PILOT_A] = {str(VELD): 100}
        self.poll(PILOT_A)
        self.read_all("start")
        self.ledger[PILOT_A] = {str(VELD): 400}
        self.read_all("poll")
        self.poll()
        self.esi_down = True
        [segment] = self.segments(PILOT_A)

        self.assertFalse(mining.take_end_reading(segment.id))
        self.assertTrue(mining.take_end_reading(segment.id, final=True))

        segment.refresh_from_db()
        self.assertEqual(segment.status, Segment.STATUS_CLOSED_STALE)
        pilot = self.results()["pilots"][0]
        self.assertEqual(pilot["status"], "partial")
        self.assertEqual(pilot["ores"][0]["quantity"], 300)

    def test_no_start_reading_ends_as_failed(self):
        self.esi_down = True
        self.poll(PILOT_A)
        self.read_all("start")
        self.poll()
        [segment] = self.segments(PILOT_A)
        mining.take_end_reading(segment.id, final=True)
        segment.refresh_from_db()
        self.assertEqual(segment.status, Segment.STATUS_FAILED)
        self.assertEqual(self.results()["pilots"][0]["ores"], [])

    def test_lower_reading_is_ignored(self):
        self.ledger[PILOT_A] = {str(VELD): 100}
        self.poll(PILOT_A)
        self.read_all("start")
        self.ledger[PILOT_A] = {str(VELD): 500}
        self.read_all("poll")
        self.ledger[PILOT_A] = {str(VELD): 200}  # stale ESI cache
        self.read_all("poll")
        quantity = self.results()["pilots"][0]["ores"][0]["quantity"]
        self.assertEqual(quantity, 400)

    def test_fleet_without_tracking_records_leaves_but_no_stints(self):
        self.fleet.track_mining = False
        self.fleet.save()
        self.instance.refresh_from_db()
        self.poll(PILOT_A)
        self.poll()
        self.assertFalse(Segment.objects.exists())
        member = EveFleetInstanceMember.objects.get(character_id=PILOT_A)
        self.assertIsNotNone(member.left_at)
        self.assertIsNotNone(member.last_seen_at)

    def test_hidden_pilots_keep_their_ore_but_lose_their_name(self):
        self.ledger[PILOT_A] = {str(VELD): 0}
        self.ledger[PILOT_B] = {str(VELD): 0}
        self.poll(PILOT_A, PILOT_B)
        self.read_all("start")
        self.ledger[PILOT_A] = {str(VELD): 10}
        self.ledger[PILOT_B] = {str(VELD): 30}
        self.read_all("poll")

        result = self.results(
            name_pilot=lambda cid, name: (
                (cid, name) if cid == PILOT_A else (None, None)
            )
        )
        names = [p["character_name"] for p in result["pilots"]]
        self.assertEqual(names, [None, "Miner A"])
        self.assertIsNone(result["pilots"][0]["character_id"])
        self.assertEqual(result["ores"][0]["quantity"], 40)


class DueSegmentsTests(MiningTestBase):
    def test_due_readings(self):
        self.poll(PILOT_A, PILOT_B)
        a, b = self.segments(PILOT_A)[0], self.segments(PILOT_B)[0]
        now = timezone.now()
        Segment.objects.filter(pk=a.pk).update(
            started_at=now - timedelta(minutes=5)
        )
        # Still inside the start task's own retries.
        self.assertEqual(mining.due_segments(now)["start"], [])
        Segment.objects.filter(pk=a.pk).update(
            started_at=now - timedelta(minutes=20)
        )
        self.assertEqual(mining.due_segments(now)["start"], [a.pk])

        mining.take_start_reading(a.pk)
        mining.take_start_reading(b.pk)
        Segment.objects.filter(pk=a.pk).update(
            latest_read_at=now - timedelta(minutes=20)
        )
        self.assertEqual(mining.due_segments(now)["poll"], [a.pk])

        self.poll()
        Segment.objects.filter(pk=b.pk).update(
            ended_at=now - timedelta(hours=1)
        )
        self.assertEqual(mining.due_segments(now)["end"], [b.pk])
        # An ended fleet is no longer polled.
        self.instance.end_time = now
        self.instance.save()
        self.assertEqual(mining.due_segments(now)["poll"], [])


class LedgerTotalsTests(MiningTestBase):
    def test_totals_since_a_day_sum_every_system(self):
        character = EveCharacter.objects.get(character_id=PILOT_A)
        veld = EveType.objects.get(id=VELD)
        for day, system, qty in (
            (date(2026, 11, 1), 1, 5),
            (date(2026, 11, 2), 1, 10),
            (date(2026, 11, 2), 2, 20),
            (date(2026, 11, 3), 3, 40),
        ):
            EveCharacterMiningEntry.objects.create(
                character=character,
                eve_type=veld,
                date=day,
                solar_system_id=system,
                quantity=qty,
            )
        self.assertEqual(
            mining_totals_since(character, date(2026, 11, 2)),
            {str(VELD): 70},
        )


class MiningEndpointTests(MiningTestBase):
    def test_endpoint_returns_results(self):
        self.ledger[PILOT_A] = {str(VELD): 0}
        self.poll(PILOT_A)
        self.read_all("start")
        self.ledger[PILOT_A] = {str(VELD): 50}
        self.read_all("poll")

        response = self.call("get", f"/{self.fleet.id}/mining", self.fc)

        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertTrue(body["track_mining"])
        self.assertTrue(body["measuring"])
        self.assertEqual(body["pilots"][0]["character_name"], "Miner A")
        self.assertEqual(body["pilots"][0]["ores"][0]["quantity"], 50)

    def test_unknown_fleet_is_404(self):
        response = self.call("get", "/999999/mining", self.fc)
        self.assertEqual(response.status_code, 404)


class TimelineTests(MiningTestBase):
    def delta(self, character_id, minutes, quantity, type_id=VELD):
        EveCharacterMiningDelta.objects.create(
            character=EveCharacter.objects.get(character_id=character_id),
            eve_type_id=type_id,
            solar_system_id=SYSTEM,
            quantity=quantity,
            observed_at=self.t0 + timedelta(minutes=minutes),
        )
        # The read that saw it is stamped a moment after the row is saved.
        self.read(character_id, minutes, seconds=1)

    def read(self, character_id, minutes, seconds=0):
        """A ledger read at t0 + minutes, stamped on the pilot's stints."""
        at = self.t0 + timedelta(minutes=minutes, seconds=seconds)
        for segment in self.segments(character_id):
            segment.read_times = list(segment.read_times) + [at.isoformat()]
            segment.save(update_fields=["read_times"])

    def setUp(self):
        super().setUp()
        now = timezone.now()
        self.t0 = mining._Buckets(  # pylint: disable=protected-access
            now, now
        ).first - timedelta(hours=2)
        EveFleetInstance.objects.filter(pk=self.instance.pk).update(
            start_time=self.t0
        )
        self.poll(PILOT_A, PILOT_B)
        self.read_all("start")
        Segment.objects.update(started_at=self.t0, start_read_at=self.t0)
        b = self.segments(PILOT_B)[0]
        Segment.objects.filter(pk=b.pk).update(
            started_at=self.t0 + timedelta(minutes=30),
            start_read_at=self.t0 + timedelta(minutes=30),
        )

    def timeline(self):
        return mining.fleet_mining_timeline(
            self.fleet,
            lambda cid, name: (cid, name),
            now=self.t0 + timedelta(minutes=89),
        )

    def test_buckets_cells_and_idle(self):
        self.delta(PILOT_A, -5, 999)  # before the start reading: excluded
        self.delta(PILOT_A, 5, 1000)  # bucket 0
        self.delta(PILOT_A, 20, 1000)  # bucket 1
        self.read(PILOT_A, 35)  # reads that found nothing
        self.read(PILOT_A, 50)
        self.read(PILOT_A, 65)
        self.delta(PILOT_A, 80, 1000)  # spread over 65-80: buckets 4, 5
        self.delta(PILOT_B, 25, 500)  # before B's start reading: excluded
        self.delta(PILOT_B, 40, 500)  # spread over 30-40: bucket 2
        self.read(PILOT_B, 55)
        self.read(PILOT_B, 70)
        self.read(PILOT_B, 85)

        result = self.timeline()

        self.assertEqual(result["bucket_minutes"], 15)
        self.assertEqual(len(result["buckets"]), 6)
        a, b = result["pilots"]
        self.assertEqual(a["character_name"], "Miner A")
        # 20's ore covers 5-20, so it reaches into bucket 1; 2 and 3 had
        # only empty reads.
        self.assertEqual(
            a["cells"], ["ore", "ore", "idle", "idle", "ore", "ore"]
        )
        self.assertEqual(a["volume_m3"], 300.0)
        self.assertEqual(a["mining_pct"], 67)
        self.assertEqual(
            b["cells"], ["out", "out", "ore", "idle", "idle", "idle"]
        )
        self.assertEqual(b["volume_m3"], 50.0)
        # 100 from 0-5, plus 10 of the 15 minutes 5-20 covers.
        self.assertAlmostEqual(result["totals_m3"][0], 166.67, delta=0.5)
        self.assertEqual(result["totals_m3"][2], 50.0)

    def test_single_empty_bucket_is_quiet_not_idle(self):
        self.delta(PILOT_A, 5, 100)
        self.read(PILOT_A, 15)
        self.read(PILOT_A, 30)
        self.delta(PILOT_A, 40, 100)  # covers 30-40 only
        cells = self.timeline()["pilots"][0]["cells"]
        self.assertEqual(cells[:3], ["ore", "quiet", "ore"])

    def test_ore_after_leaving_is_cut_at_the_end_reading(self):
        self.delta(PILOT_A, 5, 100)
        self.read(PILOT_A, 20)
        self.poll(PILOT_B)  # A leaves
        a = self.segments(PILOT_A)[0]
        Segment.objects.filter(pk=a.pk).update(
            ended_at=self.t0 + timedelta(minutes=30),
            latest_read_at=self.t0 + timedelta(minutes=41),
            status=Segment.STATUS_CLOSED,
        )
        self.delta(PILOT_A, 40, 200)  # seen by the end reading: counted
        self.delta(PILOT_A, 60, 900)  # after: solo mining, not counted
        pilot = next(
            p
            for p in self.timeline()["pilots"]
            if p["character_name"] == "Miner A"
        )
        self.assertEqual(pilot["volume_m3"], 30.0)
        # The end reading's ore covers 20 up to the leave at 30.
        self.assertEqual(pilot["cells"][1], "ore")
        self.assertEqual(pilot["cells"][2], "quiet")
        self.assertEqual(pilot["cells"][3:], ["out", "out", "out"])

    def test_log_is_newest_first_with_joins(self):
        self.delta(PILOT_A, 5, 100)
        events = self.timeline()["events"]
        self.assertEqual(events[0]["kind"], "join")  # B at +30
        kinds = [e["kind"] for e in events]
        self.assertIn("ore", kinds)
        self.assertEqual(kinds.count("join"), 2)

    def test_no_instance_is_none(self):
        self.instance.delete()
        self.assertIsNone(self.timeline())

    def test_endpoint_includes_timeline(self):
        self.delta(PILOT_A, 5, 100)
        body = self.call("get", f"/{self.fleet.id}/mining", self.fc).json()
        self.assertEqual(body["timeline"]["bucket_minutes"], 15)
        self.assertTrue(body["timeline"]["pilots"])


class TimelineFallbackTests(TimelineTests):
    def test_readings_fill_in_when_no_deltas_were_stored(self):
        a = self.segments(PILOT_A)[0]
        Segment.objects.filter(pk=a.pk).update(
            start_totals={str(VELD): 100},
            latest_totals={str(VELD): 600},
            latest_read_at=self.t0 + timedelta(minutes=50),
        )
        pilot = next(
            p
            for p in self.timeline()["pilots"]
            if p["character_name"] == "Miner A"
        )
        self.assertEqual(pilot["volume_m3"], 50.0)
        self.assertEqual(pilot["cells"][3], "ore")


class TimelineMixedTests(TimelineTests):
    def test_untimed_ore_stays_once_delta_rows_start(self):
        a = self.segments(PILOT_A)[0]
        Segment.objects.filter(pk=a.pk).update(
            start_totals={str(VELD): 0},
            latest_totals={str(VELD): 1500},
            latest_read_at=self.t0 + timedelta(minutes=80),
        )
        self.read(PILOT_A, 60)
        self.delta(PILOT_A, 70, 300)  # only the last 500 were timed
        self.delta(PILOT_A, 80, 200)
        pilot = next(
            p
            for p in self.timeline()["pilots"]
            if p["character_name"] == "Miner A"
        )
        self.assertEqual(pilot["volume_m3"], 150.0)  # all 1500 units
        # 1000 untimed at 70, 300 over 60-70, half of 200 over 70-80.
        self.assertAlmostEqual(pilot["cell_m3"][4], 140.0, delta=0.5)
        self.assertAlmostEqual(pilot["cell_m3"][5], 10.0, delta=0.5)


class LedgerReadStampTests(MiningTestBase):
    """Every ledger read, the scheduler's included, is stamped on stints."""

    def setUp(self):
        super().setUp()
        self.poll(PILOT_A, PILOT_B)
        self.ledger[PILOT_A] = {str(VELD): 100}
        self.read_all("start")
        self.character_a = EveCharacter.objects.get(character_id=PILOT_A)

    def ledger_row(self, quantity):
        EveCharacterMiningEntry.objects.update_or_create(
            character=self.character_a,
            eve_type_id=VELD,
            date=timezone.now().date(),
            solar_system_id=SYSTEM,
            defaults={"quantity": quantity},
        )

    def test_an_open_stint_takes_the_read_as_its_latest_reading(self):
        self.ledger_row(700)
        at = timezone.now()
        mining_ledger_read.send(
            sender=None, character=self.character_a, read_at=at
        )
        a = self.segments(PILOT_A)[0]
        self.assertEqual(a.read_times, [at.isoformat()])
        self.assertEqual(a.latest_totals, {str(VELD): 700})
        self.assertEqual(a.latest_read_at, at)
        # So our own live poll isn't due.
        self.assertNotIn(a.pk, mining.due_segments()["poll"])
        # Other pilots aren't touched.
        self.assertEqual(self.segments(PILOT_B)[0].read_times, [])

    def test_a_closing_stint_is_stamped_but_keeps_its_totals(self):
        self.poll(PILOT_B)  # A leaves
        self.ledger_row(900)
        mining_ledger_read.send(
            sender=None, character=self.character_a, read_at=timezone.now()
        )
        a = self.segments(PILOT_A)[0]
        self.assertEqual(a.status, Segment.STATUS_CLOSING)
        self.assertEqual(len(a.read_times), 1)
        self.assertEqual(a.latest_totals, {str(VELD): 100})

    def test_no_stamp_once_track_mining_is_off(self):
        self.fleet.track_mining = False
        self.fleet.save()
        mining_ledger_read.send(
            sender=None, character=self.character_a, read_at=timezone.now()
        )
        self.assertEqual(self.segments(PILOT_A)[0].read_times, [])

    def test_sync_sends_the_read_even_with_no_new_ore(self):
        response = MagicMock()
        response.success.return_value = True
        response.results.return_value = []
        received = []

        def listener(sender, character, read_at, **kwargs):
            received.append((character.character_id, read_at))

        mining_ledger_read.connect(listener)
        self.addCleanup(mining_ledger_read.disconnect, listener)
        with patch("eveonline.helpers.characters.mining.EsiClient") as client:
            client.return_value.get_character_mining_ledger.return_value = (
                response
            )
            sync_character_mining(self.character_a)
        self.assertEqual([r[0] for r in received], [PILOT_A])

    def test_failed_sync_sends_nothing(self):
        response = MagicMock()
        response.success.return_value = False
        received = []

        def listener(sender, **kwargs):
            received.append(kwargs)

        mining_ledger_read.connect(listener)
        self.addCleanup(mining_ledger_read.disconnect, listener)
        with patch("eveonline.helpers.characters.mining.EsiClient") as client:
            client.return_value.get_character_mining_ledger.return_value = (
                response
            )
            self.assertIsNone(sync_character_mining(self.character_a))
        self.assertEqual(received, [])


class DueModeTests(MiningTestBase):
    def setUp(self):
        super().setUp()
        self.poll(PILOT_A)
        self.read_all("start")
        self.a = self.segments(PILOT_A)[0]

    def read_ago(self, minutes):
        Segment.objects.filter(pk=self.a.pk).update(
            latest_read_at=timezone.now() - timedelta(minutes=minutes)
        )

    @override_settings(CHARACTER_SYNC_MODE="scheduled")
    def test_scheduled_mode_only_polls_as_a_fallback(self):
        self.read_ago(20)  # the scheduler is due about now
        self.assertEqual(mining.due_segments()["poll"], [])
        self.read_ago(30)  # it missed this pilot
        self.assertEqual(mining.due_segments()["poll"], [self.a.pk])

    @override_settings(CHARACTER_SYNC_MODE="fanout")
    def test_fanout_mode_polls_every_interval(self):
        self.read_ago(20)
        self.assertEqual(mining.due_segments()["poll"], [self.a.pk])

    def test_track_mining_off_stops_polls(self):
        self.read_ago(30)
        self.fleet.track_mining = False
        self.fleet.save()
        self.assertEqual(mining.due_segments()["poll"], [])


@patch("fleets.endpoints.helpers.queue_channel_message")
class TrackMiningOffTests(MiningTestBase):
    def test_switching_off_closes_open_stints(self, _):
        self.poll(PILOT_A, PILOT_B)
        self.read_all("start")
        response = self.call(
            "patch", f"/{self.fleet.id}", self.fc, {"track_mining": False}
        )
        self.assertEqual(response.status_code, 200, response.content)
        statuses = set(Segment.objects.values_list("status", flat=True))
        self.assertEqual(statuses, {Segment.STATUS_CLOSING})
        # Members seen later don't open new stints.
        self.instance = EveFleetInstance.objects.get(pk=self.instance.pk)
        self.poll(PILOT_A, PILOT_B)
        self.assertEqual(Segment.objects.count(), 2)


class EmptyMemberPollTests(MiningTestBase):
    def test_empty_answer_does_not_mark_everyone_left(self):
        self.poll(PILOT_A, PILOT_B)
        response = MagicMock()
        response.success.return_value = True
        response.results.return_value = []
        with patch.object(EveFleetInstance, "esi_client") as esi_client, patch(
            "fleets.models.EsiClient"
        ) as names:
            esi_client.return_value.get_fleet_members.return_value = response
            names.return_value.resolve_universe_names.return_value.results.return_value = (
                []
            )
            self.instance.update_fleet_members()
        self.assertFalse(
            EveFleetInstanceMember.objects.filter(
                left_at__isnull=False
            ).exists()
        )
        self.assertEqual(
            Segment.objects.filter(ended_at__isnull=True).count(), 2
        )


class UnstampedSpreadTests(TimelineTests):
    def test_rows_with_no_stamped_read_cover_at_most_the_fleet_interval(self):
        EveCharacterMiningDelta.objects.create(
            character=EveCharacter.objects.get(character_id=PILOT_A),
            eve_type_id=VELD,
            solar_system_id=SYSTEM,
            quantity=1500,
            observed_at=self.t0 + timedelta(minutes=60),
        )
        pilot = self.timeline()["pilots"][0]
        # 45-60 only: buckets 0-2 stay empty.
        self.assertEqual(pilot["cell_m3"][3], 150.0)
        self.assertEqual(pilot["cells"][:3], ["idle", "idle", "idle"])


class PilotNamerTests(MiningTestBase):
    def setUp(self):
        super().setUp()
        _system(SYSTEM, "Amamake", 0.4, 10000042, "Heimatar")
        _system(HIGH_SYSTEM, "Rens", 0.9, 10000030, "Heimatar")
        self.poll(PILOT_A, PILOT_B)
        self.ledger[PILOT_A] = {str(VELD): 0}
        self.ledger[PILOT_B] = {str(VELD): 0}
        self.read_all("start")
        self.ledger[PILOT_A] = {str(VELD): 100}
        self.ledger[PILOT_B] = {str(VELD): 100}
        self.read_all("poll")
        for character_id, system in (
            (PILOT_A, SYSTEM),
            (PILOT_B, HIGH_SYSTEM),
        ):
            EveCharacterMiningDelta.objects.create(
                character=EveCharacter.objects.get(character_id=character_id),
                eve_type_id=VELD,
                solar_system_id=system,
                quantity=100,
                # Just after the start reading, so before "now".
                observed_at=self.segments(character_id)[0].start_read_at
                + timedelta(microseconds=100),
            )

    def namer(self, **kwargs):
        options = {
            "sees_everyone": False,
            "roster_shown": True,
            "own_ids": set(),
        }
        options.update(kwargs)
        return mining.pilot_namer(self.fleet, **options)

    def test_outside_high_sec_is_undisclosed(self):
        name = self.namer()
        self.assertEqual(name(PILOT_A, "Miner A"), (None, UNDISCLOSED))
        self.assertEqual(name(PILOT_B, "Miner B"), (PILOT_B, "Miner B"))

    def test_fc_and_own_pilots_see_the_real_name(self):
        self.assertEqual(
            self.namer(sees_everyone=True)(PILOT_A, "Miner A"),
            (PILOT_A, "Miner A"),
        )
        self.assertEqual(
            self.namer(own_ids={PILOT_A})(PILOT_A, "Miner A"),
            (PILOT_A, "Miner A"),
        )

    def test_hidden_roster_hides_every_other_name(self):
        name = self.namer(roster_shown=False)
        self.assertEqual(name(PILOT_B, "Miner B"), (None, None))

    def test_results_keep_undisclosed_ore_in_the_totals(self):
        result = mining.fleet_mining_results(self.fleet, self.namer())
        names = {p["character_name"] for p in result["pilots"]}
        self.assertEqual(names, {UNDISCLOSED, "Miner B"})
        self.assertEqual(result["ores"][0]["quantity"], 200)
