"""The /landing-new heartbeat and week table: totals, the Live band's pilot
lines, Fleet activity engagements, mining from ledger deltas and the 60-minute
delay on fleets and comms."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone

from alliance.helpers.landing_pulse import build_fast, build_slow
from alliance.helpers.landing_week import build_week, landing_week
from app.test import TestCase
from discord.models import DiscordChannelActivityRecord, DiscordUser
from eveonline.constants import (
    AMARR_FACTION_ID,
    MINMATAR_FLEET_ALLIANCE_ID,
)
from eveonline.helpers.characters import set_primary_character
from eveonline.helpers.characters.mining import _record_delta
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
    EveCharacterMiningDelta,
)
from eveuniverse.models import EveCategory, EveGroup, EveType
from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember
from fleets.tests import disconnect_fleet_signals

ENEMY_ALLIANCE_ID = 99000001
OTHER_ENEMY_ALLIANCE_ID = 99000002


class LandingPulseTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.now = timezone.now()
        self.pilot = EveCharacter.objects.create(
            character_id=2001,
            character_name="Orion Sa-Solo",
            alliance_id=MINMATAR_FLEET_ALLIANCE_ID,
        )
        self.wingman = EveCharacter.objects.create(
            character_id=2002,
            character_name="Ender Locke",
            alliance_id=MINMATAR_FLEET_ALLIANCE_ID,
        )
        EveAlliance.objects.create(
            alliance_id=ENEMY_ALLIANCE_ID, name="Snuffed Out"
        )
        EveAlliance.objects.create(
            alliance_id=OTHER_ENEMY_ALLIANCE_ID, name="Templis CALSF"
        )
        category, _ = EveCategory.objects.get_or_create(
            id=6, defaults={"name": "Ship", "published": True}
        )
        group, _ = EveGroup.objects.get_or_create(
            id=25,
            defaults={
                "name": "Frigate",
                "published": True,
                "eve_category": category,
            },
        )
        EveType.objects.get_or_create(
            id=587,
            defaults={"name": "Rifter", "published": True, "eve_group": group},
        )

    def _large_fleet(self, character, start, end):
        """A fleet of LARGE_FLEET_PILOTS with ``character`` in it."""
        disconnect_fleet_signals()
        fc = User.objects.create(username="fc")
        fleet = EveFleet.objects.create(
            start_time=start,
            type="strategic",
            status="complete",
            created_by=fc,
        )
        instance = EveFleetInstance.objects.create(id=4242, eve_fleet=fleet)
        EveFleetInstance.objects.filter(pk=instance.pk).update(
            start_time=start, end_time=end
        )
        for index in range(10):
            EveFleetInstanceMember.objects.create(
                eve_fleet_instance=instance,
                character_id=(
                    character.character_id if index == 0 else 8000 + index
                ),
                character_name=f"Pilot {index}",
                role="squad_member",
                role_name="Squad Member",
                ship_type_id=587,
                ship_name="Rifter",
                solar_system_id=30002537,
                solar_system_name="Amamake",
                squad_id=1,
                wing_id=1,
            )

    def _killmail(self, row_id, killmail_id, character, ago, **victim):
        return EveCharacterKillmail.objects.create(
            id=row_id,
            killmail_id=killmail_id,
            killmail_hash=f"h{row_id}",
            killmail_time=self.now - ago,
            solar_system_id=30002537,
            ship_type_id=587,
            attackers="[]",
            items="[]",
            character=character,
            **victim,
        )

    def _event_actions(self, data):
        return [
            (e["character_name"], e["others"], e["action"])
            for e in data["events"]
        ]

    def _week_actions(self, tab):
        return [
            (e["character_name"], e["others"], e["action"])
            for e in build_week(self.now)["tabs"][tab]
        ]

    def test_small_gang_kill_names_the_hull_and_counts_our_pilots(self):
        for row_id, character in ((1, self.pilot), (2, self.wingman)):
            self._killmail(
                row_id,
                500,
                character,
                timedelta(hours=2),
                victim_character_id=9001,
                victim_alliance_id=ENEMY_ALLIANCE_ID,
            )

        data = build_fast(self.now)

        self.assertEqual(data["day"]["ships_destroyed"], 1)
        self.assertEqual(data["week"]["ships_destroyed"], 1)
        self.assertEqual(
            self._event_actions(data),
            [("Orion Sa-Solo", 1, "killed a Rifter")],
        )
        self.assertEqual(sum(h["kills"] for h in data["hourly_kills"]), 1)
        self.assertEqual(len(data["hourly_kills"]), 24)
        line = data["events"][0]
        self.assertEqual(
            (line["verb"], line["subject"], line["subject_type"]),
            ("killed a", "Rifter", "type"),
        )
        self.assertEqual(line["subject_id"], 587)

    def test_large_fleet_kill_names_the_victims_alliance(self):
        self._large_fleet(
            self.pilot,
            self.now - timedelta(hours=3),
            self.now - timedelta(hours=1),
        )
        self._killmail(
            1,
            500,
            self.pilot,
            timedelta(hours=2),
            victim_character_id=9001,
            victim_alliance_id=ENEMY_ALLIANCE_ID,
        )

        data = build_fast(self.now)

        # A fleet fight is Fleet activity, not a Live band line.
        self.assertEqual(data["events"], [])
        self.assertIn(
            ("Orion Sa-Solo", 0, "fought Snuffed Out and won"),
            self._week_actions("kills"),
        )
        row = build_week(self.now)["tabs"]["kills"][0]
        self.assertEqual(
            (row["subject_type"], row["subject_id"]),
            ("alliance", ENEMY_ALLIANCE_ID),
        )

    def test_solo_loss_names_the_hull(self):
        self._killmail(
            3,
            501,
            self.pilot,
            timedelta(hours=3),
            victim_character_id=self.pilot.character_id,
            victim_alliance_id=MINMATAR_FLEET_ALLIANCE_ID,
        )

        data = build_fast(self.now)

        self.assertEqual(
            self._event_actions(data), [("Orion Sa-Solo", 0, "lost a Rifter")]
        )

    def test_large_fleet_loss_names_the_largest_attacking_alliance(self):
        self._large_fleet(
            self.pilot,
            self.now - timedelta(hours=4),
            self.now - timedelta(hours=2),
        )
        killmail = self._killmail(
            3,
            501,
            self.pilot,
            timedelta(hours=3),
            victim_character_id=self.pilot.character_id,
            victim_alliance_id=MINMATAR_FLEET_ALLIANCE_ID,
        )
        for character_id, alliance_id in (
            (9101, OTHER_ENEMY_ALLIANCE_ID),
            (9102, OTHER_ENEMY_ALLIANCE_ID),
            (9103, ENEMY_ALLIANCE_ID),
        ):
            EveCharacterKillmailAttacker.objects.create(
                killmail=killmail,
                character_id=character_id,
                alliance_id=alliance_id,
            )

        data = build_fast(self.now)

        self.assertEqual(data["day"]["ships_lost"], 1)
        self.assertEqual(data["day"]["ships_destroyed"], 0)
        self.assertIn(
            (
                "Orion Sa-Solo",
                0,
                "fought Templis CALSF and went down swinging",
            ),
            self._week_actions("kills"),
        )

    def test_kills_are_live(self):
        self._killmail(
            4,
            502,
            self.pilot,
            timedelta(minutes=20),
            victim_character_id=9001,
            victim_alliance_id=ENEMY_ALLIANCE_ID,
        )

        data = build_fast(self.now)

        self.assertEqual(data["day"]["ships_destroyed"], 1)
        self.assertEqual(
            self._event_actions(data),
            [("Orion Sa-Solo", 0, "killed a Rifter")],
        )

    def test_fleets_from_the_last_hour_are_held_back(self):
        self._large_fleet(
            self.pilot,
            self.now - timedelta(hours=2),
            self.now - timedelta(minutes=20),
        )

        data = build_fast(self.now)

        self.assertEqual(
            [e for e in data["events"] if e["kind"] == "fleet"], []
        )

    def test_comms_from_the_last_hour_are_held_back(self):
        user = User.objects.create(username="voice")
        DiscordUser.objects.create(id=7100, discord_tag="bear", user=user)
        character = EveCharacter.objects.create(
            character_id=2100, character_name="BearThatCares", user=user
        )
        set_primary_character(user, character)
        minute = (self.now - timedelta(minutes=20)).replace(
            second=0, microsecond=0
        )
        for tag in ("anna", "bear", "cass"):
            record = DiscordChannelActivityRecord.objects.create(
                activity_type=DiscordChannelActivityRecord.VOICE_MINUTE,
                username=tag,
                quantity=1,
                channel_name="Ops 1",
            )
            DiscordChannelActivityRecord.objects.filter(pk=record.pk).update(
                created_on=minute
            )

        data = build_fast(self.now)

        self.assertEqual(data["week"]["peak_comms"], 0)
        self.assertEqual(data["events"], [])

    def test_solo_kill_on_a_militia_pilot(self):
        self._killmail(
            5,
            503,
            self.pilot,
            timedelta(hours=2),
            victim_character_id=9001,
            victim_faction_id=AMARR_FACTION_ID,
        )

        data = build_fast(self.now)

        self.assertEqual(
            self._event_actions(data),
            [("Orion Sa-Solo", 0, "killed a Rifter")],
        )

    def test_voice_counts_toward_peak_comms_only(self):
        minute = (self.now - timedelta(hours=2)).replace(
            second=0, microsecond=0
        )
        for index, tag in enumerate(("anna", "bear", "cass")):
            user = User.objects.create(username=f"voice{index}")
            DiscordUser.objects.create(
                id=7000 + index, discord_tag=tag, user=user
            )
            if tag == "bear":
                character = EveCharacter.objects.create(
                    character_id=2100,
                    character_name="BearThatCares",
                    user=user,
                )
                set_primary_character(user, character)
            record = DiscordChannelActivityRecord.objects.create(
                activity_type=DiscordChannelActivityRecord.VOICE_MINUTE,
                username=tag,
                quantity=1,
                channel_name="Ops 1",
            )
            DiscordChannelActivityRecord.objects.filter(pk=record.pk).update(
                created_on=minute
            )

        data = build_fast(self.now)

        self.assertEqual(data["week"]["peak_comms"], 3)
        self.assertEqual(data["events"], [])
        self.assertNotIn("Ops 1", str(data))

    def _ore(self):
        category, _ = EveCategory.objects.get_or_create(
            id=25, defaults={"name": "Asteroid", "published": True}
        )
        group, _ = EveGroup.objects.get_or_create(
            id=462,
            defaults={
                "name": "Veldspar",
                "published": True,
                "eve_category": category,
            },
        )
        ore, _ = EveType.objects.get_or_create(
            id=1230,
            defaults={
                "name": "Veldspar",
                "published": True,
                "eve_group": group,
                "volume": 0.1,
            },
        )
        return ore

    def test_ledger_sync_records_only_what_was_added(self):
        ore = self._ore()
        today = self.now.date()
        _record_delta(self.pilot, ore, 30002537, today, 1000, None)
        _record_delta(self.pilot, ore, 30002537, today, 1500, 1000)
        _record_delta(self.pilot, ore, 30002537, today, 1500, 1500)
        _record_delta(
            self.pilot, ore, 30002537, today - timedelta(days=5), 900, None
        )

        self.assertEqual(
            list(
                EveCharacterMiningDelta.objects.values_list(
                    "quantity", flat=True
                ).order_by("quantity")
            ),
            [500, 1000],
        )

    def test_mining_lines_and_volume_come_from_deltas(self):
        ore = self._ore()
        EveCharacterMiningDelta.objects.create(
            character=self.pilot,
            eve_type=ore,
            solar_system_id=30002537,
            quantity=420000,
            observed_at=self.now - timedelta(minutes=30),
        )

        data = build_fast(self.now)

        self.assertEqual(data["day"]["mined_volume"], 42000)
        self.assertEqual(
            self._event_actions(data),
            [("Orion Sa-Solo", 0, "mined 42,000 m³ of Veldspar")],
        )
        self.assertEqual(len(build_week(self.now)["tabs"]["mining"]), 1)

    def test_fleet_activity_groups_a_gang_and_skips_solo(self):
        # Two of ours on two kills in the same system within 20 minutes...
        for row_id, killmail_id, character, ago in (
            (11, 600, self.pilot, timedelta(hours=3)),
            (12, 601, self.wingman, timedelta(hours=3, minutes=-10)),
        ):
            self._killmail(
                row_id,
                killmail_id,
                character,
                ago,
                victim_character_id=9001,
                victim_alliance_id=ENEMY_ALLIANCE_ID,
            )
        # ...and a solo kill a day earlier, which stays out.
        self._killmail(
            13,
            602,
            self.pilot,
            timedelta(days=1),
            victim_character_id=9002,
            victim_alliance_id=ENEMY_ALLIANCE_ID,
        )

        rows = build_week(self.now)["tabs"]["fights"]

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["others"], 1)
        self.assertEqual(rows[0]["verb"], "fought")
        self.assertEqual(rows[0]["subject"], "Snuffed Out")
        self.assertTrue(rows[0]["tail"].startswith("· Small gang · 2 kills"))

    def test_week_pages_twelve_rows(self):
        for index in range(13):
            self._killmail(
                100 + index,
                700 + index,
                self.pilot,
                timedelta(hours=2, minutes=index),
                victim_character_id=9001,
                victim_alliance_id=ENEMY_ALLIANCE_ID,
            )

        first = landing_week("kills", 1)
        last = landing_week("kills", 9)

        self.assertEqual((first["pages"], first["total"]), (2, 13))
        self.assertEqual(len(first["rows"]), 12)
        self.assertEqual((last["page"], len(last["rows"])), (2, 1))
        self.assertEqual(first["counts"]["kills"], 13)
        self.assertEqual(landing_week("nonsense", 1)["tab"], "fights")

    def test_month_moments_and_timezone_chart(self):
        self._killmail(
            6,
            504,
            self.pilot,
            timedelta(days=3),
            victim_character_id=9001,
            victim_alliance_id=ENEMY_ALLIANCE_ID,
        )

        data = build_slow(self.now)

        self.assertEqual(len(data["timezone_kills"]), 24)
        self.assertEqual(
            data["moments"][0]["title"], "Biggest day of the month"
        )
        self.assertEqual(data["moments"][0]["value"], 1)


class LandingPulseEndpointTestCase(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_pulse_is_public(self):
        response = self.client.get("/api/alliance/landing/pulse")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["delay_minutes"], 60)
        self.assertEqual(len(data["hourly_kills"]), 24)
        self.assertEqual(data["events"], [])

    def test_week_is_public(self):
        response = self.client.get("/api/alliance/landing/week?tab=mining")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            (data["tab"], data["page"], data["pages"]), ("mining", 1, 1)
        )
        self.assertEqual(data["per_page"], 12)
        self.assertEqual(data["rows"], [])
