"""The /landing-new heartbeat: totals, pilot events and the 60-minute delay."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.utils import timezone

from alliance.helpers.landing_pulse import build_fast, build_slow
from app.test import TestCase
from discord.models import DiscordChannelActivityRecord, DiscordUser
from eveonline.constants import MINMATAR_FLEET_ALLIANCE_ID
from eveonline.helpers.characters import set_primary_character
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
)

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

    def test_kill_names_the_victims_alliance_and_counts_our_pilots(self):
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
            [("Orion Sa-Solo", 1, "fought Snuffed Out and won")],
        )
        self.assertEqual(sum(h["kills"] for h in data["hourly_kills"]), 1)
        self.assertEqual(len(data["hourly_kills"]), 24)

    def test_loss_names_the_largest_attacking_alliance(self):
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
        self.assertEqual(
            self._event_actions(data),
            [
                (
                    "Orion Sa-Solo",
                    0,
                    "fought Templis CALSF and went down swinging",
                )
            ],
        )

    def test_the_last_hour_is_held_back(self):
        self._killmail(
            4,
            502,
            self.pilot,
            timedelta(minutes=20),
            victim_character_id=9001,
            victim_alliance_id=ENEMY_ALLIANCE_ID,
        )

        data = build_fast(self.now)

        self.assertEqual(data["day"]["ships_destroyed"], 0)
        self.assertEqual(data["events"], [])

    def test_militia_victim_without_alliance(self):
        self._killmail(
            5,
            503,
            self.pilot,
            timedelta(hours=2),
            victim_character_id=9001,
            victim_faction_id=500003,
        )

        data = build_fast(self.now)

        self.assertEqual(
            self._event_actions(data),
            [("Orion Sa-Solo", 0, "fought the Amarr Militia and won")],
        )

    def test_voice_gathering_names_one_pilot_and_counts_the_rest(self):
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
        self.assertEqual(
            self._event_actions(data),
            [("BearThatCares", 2, "were hanging out on comms")],
        )
        self.assertNotIn("Ops 1", str(data["events"]))

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

    def test_superuser_only(self):
        response = self.client.get(
            "/api/alliance/landing/pulse",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_superuser_gets_the_pulse(self):
        self.make_superuser()
        response = self.client.get(
            "/api/alliance/landing/pulse",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["delay_minutes"], 60)
        self.assertEqual(len(data["hourly_kills"]), 24)
        self.assertEqual(data["events"], [])
