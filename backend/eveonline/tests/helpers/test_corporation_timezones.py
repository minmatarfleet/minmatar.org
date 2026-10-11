from datetime import timedelta, timezone as dt_timezone

from django.db.models import signals
from django.utils import timezone

from app.test import TestCase
from eveonline.helpers.corporations.timezones import (
    observed_prime_buckets_for_users,
    weekday_distribution,
)
from eveonline.models import (
    EveCharacter,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
)
from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember


class ObservedPrimeBucketsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        signals.post_save.disconnect(
            sender=EveFleet,
            dispatch_uid="update_fleet_schedule_on_save",
        )

    def test_one_fleet_in_eu_counts(self):
        character = EveCharacter.objects.create(
            character_id=30001,
            character_name="Fleet Pilot",
            user=self.user,
        )
        fleet = EveFleet.objects.create(
            start_time=timezone.now(),
            type="training",
            created_by=self.user,
        )
        instance = EveFleetInstance.objects.create(id=9001, eve_fleet=fleet)
        member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=character.character_id,
            character_name=character.character_name,
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=1,
            ship_name="Rifter",
            solar_system_id=1,
            solar_system_name="Amamake",
            squad_id=1,
            wing_id=1,
        )
        join_time = (
            timezone.now()
            .astimezone(dt_timezone.utc)
            .replace(hour=17, minute=0, second=0, microsecond=0)
        )
        EveFleetInstanceMember.objects.filter(pk=member.pk).update(
            join_time=join_time
        )

        buckets = observed_prime_buckets_for_users([self.user.id])
        self.assertEqual(["EU"], buckets[self.user.id])


class WeekdayDistributionTestCase(TestCase):
    def setUp(self):
        super().setUp()
        signals.post_save.disconnect(
            sender=EveFleet,
            dispatch_uid="update_fleet_schedule_on_save",
        )

    def _attend(self, character, instance_id, join_time):
        fleet = EveFleet.objects.create(
            start_time=timezone.now(),
            type="training",
            created_by=self.user,
        )
        instance = EveFleetInstance.objects.create(
            id=instance_id, eve_fleet=fleet
        )
        member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=instance,
            character_id=character.character_id,
            character_name=character.character_name,
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=1,
            ship_name="Rifter",
            solar_system_id=1,
            solar_system_name="Amamake",
            squad_id=1,
            wing_id=1,
        )
        EveFleetInstanceMember.objects.filter(pk=member.pk).update(
            join_time=join_time
        )

    def test_alts_count_once_per_eve_weekday(self):
        main = EveCharacter.objects.create(
            character_id=30011, character_name="Main", user=self.user
        )
        alt = EveCharacter.objects.create(
            character_id=30012, character_name="Alt", user=self.user
        )
        now = timezone.now().astimezone(dt_timezone.utc)
        monday = (now - timedelta(days=now.weekday() + 7)).replace(
            hour=1, minute=0, second=0, microsecond=0
        )
        self._attend(main, 9101, monday)
        self._attend(alt, 9102, monday)
        self._attend(main, 9103, monday + timedelta(days=5))

        days = weekday_distribution([self.user.id])
        self.assertEqual(7, len(days))
        self.assertEqual(1, days[0]["members"])
        self.assertEqual(1, days[5]["members"])
        self.assertEqual(0, days[2]["members"])


class KillWeekdayTestCase(TestCase):
    def test_killmail_counts_once_per_weekday(self):
        main = EveCharacter.objects.create(
            character_id=30021,
            character_name="Main",
            user=self.user,
            corporation_id=98000001,
        )
        alt = EveCharacter.objects.create(
            character_id=30022,
            character_name="Alt",
            user=self.user,
            corporation_id=98000001,
        )
        now = timezone.now().astimezone(dt_timezone.utc)
        tuesday = (now - timedelta(days=now.weekday() + 6)).replace(
            hour=12, minute=0, second=0, microsecond=0
        )
        killmail = EveCharacterKillmail.objects.create(
            id=7001,
            killmail_id=7001,
            killmail_hash="hash-7001",
            killmail_time=tuesday,
            solar_system_id=1,
            ship_type_id=1,
            victim_character_id=99999,
            attackers="[]",
            items="[]",
            character=main,
        )
        for character in (main, alt):
            EveCharacterKillmailAttacker.objects.create(
                killmail=killmail, character_id=character.character_id
            )

        days = weekday_distribution([self.user.id], 98000001)
        self.assertEqual(1, days[1]["kills"])
        self.assertEqual(1, sum(day["kills"] for day in days))
