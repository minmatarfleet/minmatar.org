"""Tests for active fleet implant polling."""

import factory
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.db.models import signals
from django.utils import timezone

from app.test import TestCase
from eveonline.client import EsiClient, EsiResponse
from fleets.helpers.active_clones import (
    FLEET_POLL_WINDOW,
    POLL_SPREAD_SECONDS,
    members_to_poll,
    poll_fleet_member_implants,
    qualifying_fleet_instances,
)
from fleets.models import (
    EveFleet,
    EveFleetAudience,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetInstanceMemberImplantSnapshot,
)
from fleets.tasks import poll_active_fleet_implants
from fleets.tests import disconnect_fleet_signals


class ActiveFleetImplantPollTest(TestCase):
    def setUp(self):
        disconnect_fleet_signals()
        super().setUp()
        self.audience = EveFleetAudience.objects.create(name="Test Audience")
        self.fleet = EveFleet.objects.create(
            audience=self.audience,
            start_time=timezone.now(),
            type="strategic",
            description="Test fleet",
        )
        self.instance = EveFleetInstance.objects.create(
            id=9001,
            eve_fleet=self.fleet,
            start_time=timezone.now(),
        )
        self.member = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=self.instance,
            character_id=12345,
            character_name="Pilot One",
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=670,
            ship_name="Thorax",
            solar_system_id=30000142,
            solar_system_name="Jita",
            squad_id=1,
            wing_id=1,
        )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_qualifying_instances_respect_45_minute_window(self):
        self.assertEqual(qualifying_fleet_instances().count(), 1)

        self.instance.start_time = timezone.now() - FLEET_POLL_WINDOW
        self.instance.save(update_fields=["start_time"])
        self.assertEqual(qualifying_fleet_instances().count(), 0)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_members_to_poll_returns_active_members(self):
        members = members_to_poll()
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].id, self.member.id)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("fleets.tasks.poll_fleet_member_implants.apply_async")
    @patch("fleets.helpers.active_clones.members_to_poll")
    def test_poll_active_fleet_implants_spreads_over_five_minutes(
        self, members_mock, apply_async_mock
    ):
        members_mock.return_value = [self.member]
        poll_active_fleet_implants()
        apply_async_mock.assert_called_once_with(
            args=[self.member.id],
            countdown=0,
        )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("fleets.tasks.poll_fleet_member_implants.apply_async")
    @patch("fleets.helpers.active_clones.members_to_poll")
    def test_poll_active_spread_for_multiple_members(
        self, members_mock, apply_async_mock
    ):
        member2 = EveFleetInstanceMember.objects.create(
            eve_fleet_instance=self.instance,
            character_id=12346,
            character_name="Pilot Two",
            role="squad_member",
            role_name="Squad Member",
            ship_type_id=670,
            ship_name="Thorax",
            solar_system_id=30000142,
            solar_system_name="Jita",
            squad_id=1,
            wing_id=1,
        )
        members_mock.return_value = [self.member, member2]
        poll_active_fleet_implants()

        self.assertEqual(apply_async_mock.call_count, 2)
        countdowns = [
            call.kwargs["countdown"]
            for call in apply_async_mock.call_args_list
        ]
        self.assertEqual(countdowns[0], 0)
        self.assertEqual(countdowns[1], int(POLL_SPREAD_SECONDS / 2))

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("fleets.helpers.active_clones.Token.get_token", return_value=True)
    @patch("fleets.helpers.active_clones.build_slot_keyed_implants")
    @patch("fleets.helpers.active_clones.get_prices_by_type_id")
    @patch("fleets.helpers.active_clones.EsiClient")
    def test_poll_member_creates_snapshot(
        self,
        esi_mock_cls,
        prices_mock,
        build_implants_mock,
        token_mock,
    ):
        build_implants_mock.return_value = {
            "perception": {"type_id": 19540, "name": "Snake Alpha"},
        }
        prices_mock.return_value = {19540: 50_000_000}

        esi = MagicMock(spec=EsiClient)
        esi_mock_cls.return_value = esi
        esi.get_character_implants.return_value = EsiResponse(
            response_code=0, data=[19540]
        )

        self.assertTrue(poll_fleet_member_implants(self.member.id))
        snapshot = EveFleetInstanceMemberImplantSnapshot.objects.get()
        self.assertEqual(snapshot.member_id, self.member.id)
        self.assertEqual(snapshot.estimated_value_isk, 50_000_000)
        self.assertEqual(
            snapshot.implants["perception"]["name"], "Snake Alpha"
        )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_poll_member_skips_after_window(self):
        self.instance.start_time = timezone.now() - (
            FLEET_POLL_WINDOW + timedelta(minutes=1)
        )
        self.instance.save(update_fields=["start_time"])
        self.assertFalse(poll_fleet_member_implants(self.member.id))
