"""Tests for tribe activity processors (occurred_at, killmail attacker logic)."""

import factory
from django.contrib.auth.models import Group, User
from django.db.models import signals as django_signals
from django.utils import timezone

from discord.signals import group_post_save, user_group_changed

from app.test import TestCase
from eveonline.models import (
    EveCharacter,
    EveCharacterKillmail,
    EveCharacterKillmailAttacker,
)
from tribes.helpers.activity_processors import (
    process_activity,
    process_killmail,
)
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupActivity,
    TribeGroupActivityRecord,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
)


def setUpModule():
    django_signals.m2m_changed.disconnect(
        user_group_changed,
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
    )
    django_signals.post_save.disconnect(
        group_post_save, sender=Group, dispatch_uid="group_post_save"
    )


class KillmailProcessorTestCase(TestCase):
    @factory.django.mute_signals(
        django_signals.pre_save, django_signals.post_save
    )
    def setUp(self):
        super().setUp()
        self.tribe = Tribe.objects.create(name="Capitals", slug="capitals")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Dreads",
            code="capitals.dreads",
        )
        self.attacker_user = User.objects.create_user(username="attacker")
        self.owner_user = User.objects.create_user(username="owner")
        self.attacker_char = EveCharacter.objects.create(
            character_id=10001,
            character_name="Attacker",
            user=self.attacker_user,
        )
        self.owner_char = EveCharacter.objects.create(
            character_id=10002,
            character_name="Owner",
            user=self.owner_user,
        )
        membership = TribeGroupMembership.objects.create(
            tribe_group=self.group,
            user=self.attacker_user,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        TribeGroupMembershipCharacter.objects.create(
            membership=membership,
            character=self.attacker_char,
        )
        self.activity = TribeGroupActivity.objects.create(
            tribe_group=self.group,
            activity_type=TribeGroupActivity.KILLMAIL,
            source_eve_type_id=23773,
        )
        kill_time = timezone.now()
        self.killmail = EveCharacterKillmail.objects.create(
            id=1,
            killmail_id=900001,
            killmail_hash="abc",
            killmail_time=kill_time,
            solar_system_id=30001,
            ship_type_id=587,
            victim_character_id=99999,
            victim_corporation_id=1,
            victim_alliance_id=1,
            victim_faction_id=None,
            attackers="[]",
            items="[]",
            character=self.owner_char,
        )
        EveCharacterKillmailAttacker.objects.create(
            killmail=self.killmail,
            character_id=self.attacker_char.character_id,
            ship_type_id=23773,
        )

    def test_credits_attacker_not_killmail_owner(self):
        created = process_killmail(self.activity)
        self.assertEqual(created, 1)
        record = TribeGroupActivityRecord.objects.get()
        self.assertEqual(record.user_id, self.attacker_user.id)
        self.assertEqual(record.character_id, self.attacker_char.id)
        self.assertEqual(record.occurred_at, self.killmail.killmail_time)

    def test_process_activity_entry_point(self):
        created = process_activity(self.activity)
        self.assertEqual(created, 1)
