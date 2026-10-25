from contextlib import ExitStack
from datetime import timedelta
from unittest import mock

import factory
from django.contrib.auth.models import Group, User
from django.db.models import signals
from django.test import override_settings
from django.utils import timezone

from app.test import TestCase
from discord.exceptions import DiscordRoleAssignmentError
from discord.models import DiscordChannelActivityRecord, DiscordUser
from eveonline.models import (
    EveCharacter,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
    EvePlayer,
)
from feed.models import FeedKillmail
from fleets.models import EveFleet, EveFleetInstance, EveFleetInstanceMember
from groups.models import UserCommunityStatus
from timezones import discord_roles, services
from timezones.activity import load_events
from timezones.models import PilotTimezone, TimezoneRole

MUTED = (signals.pre_save, signals.post_save, signals.m2m_changed)


class MuteDiscordMixin:
    """Mute model signals so groups never reach Discord in these tests."""

    def setUp(self):
        super().setUp()
        stack = ExitStack()
        stack.enter_context(factory.django.mute_signals(*MUTED))
        self.addCleanup(stack.close)


def evening_utc(days_ago, hour=23, minute=30):
    """23:30 UTC is 18:30-19:30 on the US east coast."""
    return (timezone.now() - timedelta(days=days_ago)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )


class PilotTimezoneTestCase(MuteDiscordMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = self._pilot("east_coast", 9001, "US")

    def _pilot(self, name, discord_id, prime_time, status="active"):
        user = User.objects.create(username=name)
        UserCommunityStatus.objects.create(user=user, status=status)
        DiscordUser.objects.create(id=discord_id, discord_tag=name, user=user)
        EvePlayer.objects.create(
            user=user, nickname=name, prime_time=prime_time
        )
        return user

    def _voice(self, user, when, minutes=3):
        for minute in range(minutes):
            record = DiscordChannelActivityRecord.objects.create(
                activity_type=DiscordChannelActivityRecord.VOICE_MINUTE,
                username=user.username,
                quantity=1,
            )
            DiscordChannelActivityRecord.objects.filter(pk=record.pk).update(
                created_on=when + timedelta(minutes=minute)
            )

    def test_stores_declared_inferred_and_the_answer(self):
        for day in range(1, 30, 3):
            self._voice(self.user, evening_utc(day))
        services.assess_users([self.user.id])
        row = services.timezone_for(self.user.id)
        self.assertEqual(row.declared_prime_time, "US")
        self.assertEqual(row.declared_home, "US")
        self.assertEqual(row.inferred_home, "US")
        self.assertEqual(row.home, "US")
        self.assertEqual(row.brackets, ["USTZ"])
        self.assertTrue(row.eligible)
        self.assertEqual(row.events, 10)

    def test_on_leave_pilots_keep_a_timezone_but_no_roles(self):
        away = self._pilot("away", 9002, "EU", status="on_leave")
        services.assess_users([away.id])
        row = services.timezone_for(away.id)
        self.assertEqual(row.home, "EU")
        self.assertFalse(row.eligible)
        self.assertEqual(list(services.users_in_bracket("EUTZ")), [])
        self.assertEqual(
            list(services.users_in_bracket("EUTZ", eligible_only=False)),
            [away],
        )

    def test_changes_signal_once(self):
        received = []

        def listener(sender, instance, previous_brackets, **kwargs):
            received.append((instance.user_id, previous_brackets))

        services.pilot_timezone_changed.connect(listener)
        try:
            services.assess_users([self.user.id])
            services.assess_users([self.user.id])
        finally:
            services.pilot_timezone_changed.disconnect(listener)
        self.assertEqual(received, [(self.user.id, [])])

    def test_whole_population_includes_leavers(self):
        services.assess_users()
        UserCommunityStatus.objects.filter(user=self.user).delete()
        services.assess_users()
        self.assertFalse(services.timezone_for(self.user.id).eligible)


class DeclaredChangeTestCase(TestCase):
    @factory.django.mute_signals(signals.m2m_changed)
    def test_a_new_declared_prime_time_is_assessed_straight_away(self):
        user = User.objects.create(username="declarer")
        player = EvePlayer.objects.create(user=user, nickname="declarer")
        with mock.patch(
            "timezones.tasks.assess_user_timezone.delay"
        ) as delay, self.captureOnCommitCallbacks(execute=True):
            player.prime_time = "EU"
            player.save()
        delay.assert_called_once_with(user.id)

        PilotTimezone.objects.create(
            user=user,
            declared_prime_time="EU",
            assessed_at=timezone.now(),
            changed_at=timezone.now(),
        )
        with mock.patch(
            "timezones.tasks.assess_user_timezone.delay"
        ) as delay, self.captureOnCommitCallbacks(execute=True):
            player.save()
        delay.assert_not_called()


class LoadEventsTestCase(MuteDiscordMixin, TestCase):
    def test_each_killmail_fleet_and_voice_hour_counts_once(self):
        user = User.objects.create(username="flier")
        main = EveCharacter.objects.create(
            character_id=1001, character_name="Main", user=user
        )
        EveCharacter.objects.create(
            character_id=1002, character_name="Alt", user=user
        )
        when = evening_utc(5)

        # Both characters on one ESI killmail, which the feed also has.
        killmail = EveCharacterKillmail.objects.create(
            id=1,
            killmail_id=500,
            killmail_hash="h",
            killmail_time=when,
            solar_system_id=1,
            ship_type_id=587,
            attackers="[]",
            items="[]",
            character=main,
        )
        for character_id in (1001, 1002):
            EveCharacterKillmailAttacker.objects.create(
                killmail=killmail, character_id=character_id
            )
        FeedKillmail.objects.create(
            killmail_id=500,
            hash="h",
            killmail_time=when,
            solar_system_id=1,
            attacker_summary=[{"character_id": 1001}],
            raw_killmail={},
        )
        # A feed-only loss.
        FeedKillmail.objects.create(
            killmail_id=501,
            hash="h",
            killmail_time=when + timedelta(minutes=5),
            solar_system_id=1,
            victim_character_id=1002,
            attacker_summary=[],
            raw_killmail={},
        )
        # Both characters in one fleet.
        fleet = EveFleet.objects.create(
            start_time=when, type="training", created_by=user
        )
        instance = EveFleetInstance.objects.create(id=77, eve_fleet=fleet)
        for character_id in (1001, 1002):
            member = EveFleetInstanceMember.objects.create(
                eve_fleet_instance=instance,
                character_id=character_id,
                character_name="x",
                role="squad_member",
                role_name="Squad Member",
                ship_type_id=587,
                ship_name="Rifter",
                solar_system_id=1,
                solar_system_name="Amamake",
                squad_id=1,
                wing_id=1,
            )
            EveFleetInstanceMember.objects.filter(pk=member.pk).update(
                join_time=when
            )
        # Three voice minutes in one clock hour.
        for minute in (1, 2, 3):
            record = DiscordChannelActivityRecord.objects.create(
                activity_type=DiscordChannelActivityRecord.VOICE_MINUTE,
                username="flier",
                quantity=1,
            )
            DiscordChannelActivityRecord.objects.filter(pk=record.pk).update(
                created_on=when.replace(minute=minute)
            )

        events = load_events([user.id], timezone.now() - timedelta(days=90))
        # killmail 500, killmail 501, fleet 77, one voice hour
        self.assertEqual(len(events[user.id]), 4)


@override_settings(TIMEZONES_DISCORD_ROLES=True)
class DiscordRolesTestCase(MuteDiscordMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create(username="pilot")
        self.row = PilotTimezone.objects.create(
            user=self.user,
            home="US",
            brackets=["USTZ", "EUTZ"],
            eligible=True,
            assessed_at=timezone.now(),
            changed_at=timezone.now(),
        )

    def _held(self):
        return set(
            self.user.groups.filter(timezone_role__isnull=False).values_list(
                "name", flat=True
            )
        )

    def test_eligible_pilots_get_their_brackets_and_lose_the_rest(self):
        outcome = discord_roles.apply_roles()
        self.assertEqual(outcome["added"], 2)
        self.assertEqual(self._held(), {"USTZ", "EUTZ"})
        self.assertEqual(TimezoneRole.objects.count(), 6)

        self.row.brackets = ["USTZ"]
        self.row.save()
        discord_roles.apply_roles([self.user.id])
        self.assertEqual(self._held(), {"USTZ"})

        self.row.eligible = False
        self.row.save()
        discord_roles.apply_roles()
        self.assertEqual(self._held(), set())

    def test_leaves_other_groups_alone(self):
        other = Group.objects.create(name="Corp FL33T")
        self.user.groups.add(other)
        discord_roles.apply_roles()
        self.assertIn(other, self.user.groups.all())

    def test_a_discord_failure_is_retried_next_run(self):
        def refuse(sender, action, **kwargs):
            if action == "pre_add":
                raise DiscordRoleAssignmentError("Discord is down")

        signals.m2m_changed.connect(refuse, sender=User.groups.through)
        try:
            outcome = discord_roles.apply_roles()
        finally:
            signals.m2m_changed.disconnect(refuse, sender=User.groups.through)
        self.assertEqual(outcome["failed"], 2)
        self.assertEqual(self._held(), set())

        self.assertEqual(discord_roles.apply_roles()["added"], 2)

    @override_settings(TIMEZONES_DISCORD_ROLES=False)
    def test_off_by_default(self):
        self.assertEqual(discord_roles.apply_roles(), {})
        self.assertFalse(TimezoneRole.objects.exists())
