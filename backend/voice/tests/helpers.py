"""Shared fixtures for voice tests: affiliations, features, fleets, pilots."""

import io
from datetime import timedelta
from itertools import count

import factory
from django.contrib.auth.models import Group, User
from django.db.models import signals
from django.utils import timezone

from app.test import TestCase
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter, EveCorporation
from fleets.models import EveFleet, EveFleetInstance, FleetVoiceOption
from groups.helpers.feature_access import clear_feature_cache
from groups.management.commands.sync_pilot_features import (
    Command as SyncCommand,
)
from groups.models import AffiliationType, UserAffiliation
from tribes.models import Tribe, TribeGroup, TribeGroupMembership
from voice import store
from voice.models import VoiceChannelLease, VoiceIdentity

_ids = count(90_000_001)


class VoiceTestCase(TestCase):
    def setUp(self):
        super().setUp()
        store.memory_store().flush()
        signals.post_save.disconnect(
            sender=Group, dispatch_uid="group_post_save"
        )
        signals.m2m_changed.disconnect(
            sender=User.groups.through, dispatch_uid="user_group_changed"
        )
        signals.post_save.disconnect(
            sender=EveFleet, dispatch_uid="update_fleet_schedule_on_save"
        )
        self.affiliations = {
            name: AffiliationType.objects.create(
                name=name,
                group=Group.objects.create(name=f"{name} Group"),
                priority=priority,
                default=False,
            )
            for name, priority in (
                ("Alliance", 40),
                ("Associate", 30),
                ("Militia", 20),
                ("Guest", 10),
            )
        }
        pulse = Tribe.objects.create(name="Pulse", slug="pulse")
        self.fc_group = TribeGroup.objects.create(
            tribe=pulse, name="Fleet Commanders", code="pulse.fleet-commanders"
        )
        capitals = Tribe.objects.create(name="Capitals", slug="capitals")
        self.capitals_group = TribeGroup.objects.create(
            tribe=capitals, name="Dreads", code="capitals.dreads"
        )
        clear_feature_cache()
        SyncCommand(stdout=io.StringIO(), stderr=io.StringIO()).handle()
        clear_feature_cache()
        self.mumble = FleetVoiceOption.objects.get(kind="mumble")
        self.mumble.is_active = True
        self.mumble.save()
        self.discord = FleetVoiceOption.objects.get(kind="discord")

    def tearDown(self):
        clear_feature_cache()
        store.memory_store().flush()

    def pilot(self, name, affiliation=None, *, ticker="", user=True):
        """(user or None, character) for a new pilot."""
        character_id = next(_ids)
        corporation_id = None
        if ticker:
            corporation_id = next(_ids)
            EveCorporation.objects.create(
                corporation_id=corporation_id,
                name=f"{ticker} corp",
                ticker=ticker,
            )
        django_user = None
        with factory.django.mute_signals(signals.post_save, signals.pre_save):
            if user:
                django_user = User.objects.create_user(username=name)
            character = EveCharacter.objects.create(
                character_id=character_id,
                character_name=name,
                user=django_user,
                corporation_id=corporation_id,
            )
            if django_user:
                set_primary_character(django_user, character)
        if affiliation and django_user:
            UserAffiliation.objects.create(
                user=django_user, affiliation=self.affiliations[affiliation]
            )
        clear_feature_cache()
        return django_user, character

    def alt(self, user, name):
        """A second character on the user's account (not their main)."""
        with factory.django.mute_signals(signals.post_save, signals.pre_save):
            return EveCharacter.objects.create(
                character_id=next(_ids), character_name=name, user=user
            )

    def join(self, group, user):
        with factory.django.mute_signals(signals.m2m_changed):
            TribeGroupMembership.objects.create(
                user=user,
                tribe_group=group,
                status=TribeGroupMembership.STATUS_ACTIVE,
            )
        clear_feature_cache()

    def identity(self, character):
        return VoiceIdentity.objects.create(
            character_id=character.character_id,
            character_name=character.character_name,
        )

    def fleet(self, creator=None, *, mumble=True, start_in=timedelta(0), **kw):
        with factory.django.mute_signals(signals.post_save):
            return EveFleet.objects.create(
                type="strategic",
                description="Test fleet",
                start_time=timezone.now() + start_in,
                created_by=creator,
                status="pending",
                voice_option=self.mumble if mumble else self.discord,
                **kw,
            )

    def track(self, fleet, boss_id=None):
        with factory.django.mute_signals(signals.post_save):
            return EveFleetInstance.objects.create(
                id=next(_ids), eve_fleet=fleet, boss_id=boss_id
            )

    def lease(self, fleet, branch=1):
        return VoiceChannelLease.objects.create(branch=branch, fleet=fleet)
