"""Branch leases and the grants a Mumble fleet's own data gives."""

from datetime import timedelta

import factory
from django.db.models import signals
from django.utils import timezone
from eveuniverse.models import EveCategory, EveGroup, EveType

from fleets.models import (
    EveFleetInstanceMember,
    EveFleetInvite,
    EveFleetInviteWave,
    EveFleetRoleVolunteer,
)
from voice import grants, leases
from voice.models import VoiceAuditEvent, VoiceChannelLease, VoiceGrant
from voice.tests.helpers import VoiceTestCase


class LeaseTest(VoiceTestCase):
    def setUp(self):
        super().setUp()
        self.fc_user, _ = self.pilot("fc", "Alliance")

    def test_a_tracked_mumble_fleet_wants_a_branch(self):
        fleet = self.fleet(self.fc_user)
        self.assertFalse(leases.wants_lease(fleet))
        self.track(fleet)
        self.assertTrue(leases.wants_lease(fleet))

    def test_discord_fleets_never_lease(self):
        fleet = self.fleet(self.fc_user, mumble=False)
        self.track(fleet)
        self.assertFalse(leases.wants_lease(fleet))

    def test_signups_lease_from_two_hours_before_start(self):
        fleet = self.fleet(self.fc_user, start_in=timedelta(hours=3))
        EveFleetRoleVolunteer.objects.create(
            eve_fleet=fleet, character_id=1, character_name="x", role="scout"
        )
        self.assertFalse(leases.wants_lease(fleet))
        self.assertTrue(
            leases.wants_lease(
                fleet, now=timezone.now() + timedelta(hours=1, minutes=1)
            )
        )

    def test_restricted_fleets_lease_fleet_2_and_3_only(self):
        fleets = [self.fleet(self.fc_user) for _ in range(3)]
        got = [leases.acquire(fleet) for fleet in fleets]
        self.assertEqual([lease.branch for lease in got[:2]], [2, 3])
        self.assertIsNone(got[2])
        # Asking again returns the same lease.
        self.assertEqual(leases.acquire(fleets[0]).id, got[0].id)

    def test_open_fleets_take_fleet_1_then_a_restricted_branch(self):
        first = self.fleet(self.fc_user, mumble_open=True)
        second = self.fleet(self.fc_user, mumble_open=True)
        self.assertEqual(leases.acquire(first).branch, 1)
        self.assertEqual(leases.acquire(second).branch, 2)

    def test_a_restricted_fleet_gives_up_fleet_1(self):
        fleet = self.fleet(self.fc_user, mumble_open=True)
        self.track(fleet)
        lease = self.lease(fleet, branch=1)
        self.assertIsNone(leases.release_reason(lease))
        fleet.mumble_open = False
        fleet.save()
        lease.refresh_from_db()
        self.assertEqual(leases.release_reason(lease), "access_changed")
        # An open fleet that fell back to Fleet 2 keeps it.
        other = self.fleet(self.fc_user, mumble_open=True)
        self.track(other)
        self.assertIsNone(leases.release_reason(self.lease(other, branch=2)))

    def test_no_tracking_thirty_minutes_after_start_releases(self):
        fleet = self.fleet(self.fc_user)
        lease = self.lease(fleet, branch=2)
        self.assertIsNone(leases.release_reason(lease))
        later = timezone.now() + timedelta(minutes=31)
        self.assertEqual(leases.release_reason(lease, later), "no_tracking")

    def test_closing_keeps_the_branch_thirty_more_minutes(self):
        fleet = self.fleet(self.fc_user)
        self.track(fleet)
        lease = self.lease(fleet, branch=2)
        leases.schedule_release(fleet)
        lease.refresh_from_db()
        self.assertIsNone(leases.release_reason(lease))
        self.assertEqual(
            leases.release_reason(
                lease, timezone.now() + timedelta(minutes=31)
            ),
            "closed",
        )

    def test_switching_away_from_mumble_releases_at_once(self):
        fleet = self.fleet(self.fc_user)
        self.track(fleet)
        lease = self.lease(fleet)
        fleet.voice_option = self.discord
        fleet.save()
        lease.refresh_from_db()
        self.assertEqual(leases.release_reason(lease), "voice_changed")

    def test_release_ends_the_fleets_grants(self):
        fleet = self.fleet(self.fc_user)
        lease = self.lease(fleet)
        VoiceGrant.objects.create(
            character_id=5, fleet=fleet, source=VoiceGrant.SOURCE_IN_FLEET
        )
        affected = leases.release(lease, "closed")
        self.assertEqual(affected, {5})
        self.assertFalse(
            VoiceGrant.objects.filter(expires_at__isnull=True).exists()
        )
        self.assertFalse(VoiceChannelLease.active().exists())

    def test_maintain_leases_and_releases(self):
        tracked = self.fleet(self.fc_user)
        self.track(tracked)
        stale = self.fleet(self.fc_user, start_in=timedelta(hours=-1))
        self.lease(stale, branch=3)
        result = leases.maintain()
        self.assertEqual(result["acquired"], [tracked.id])
        self.assertEqual(result["released"], [stale.id])


def _ship(type_id, group_name):
    category, _ = EveCategory.objects.get_or_create(
        id=6, defaults={"name": "Ship", "published": True}
    )
    group, _ = EveGroup.objects.get_or_create(
        id=abs(hash(group_name)) % 100000,
        defaults={
            "name": group_name,
            "eve_category": category,
            "published": True,
        },
    )
    EveType.objects.get_or_create(
        id=type_id,
        defaults={
            "name": f"ship {type_id}",
            "eve_group": group,
            "published": True,
        },
    )
    return type_id


class GrantSyncTest(VoiceTestCase):
    def setUp(self):
        super().setUp()
        self.fc_user, self.fc_char = self.pilot("fc", "Alliance")
        self.fleet_ = self.fleet(self.fc_user)
        self.instance = self.track(
            self.fleet_, boss_id=self.fc_char.character_id
        )
        self.lease(self.fleet_)

    def member(self, character_id, ship_type_id, wing_id=1):
        with factory.django.mute_signals(signals.post_save):
            return EveFleetInstanceMember.objects.create(
                eve_fleet_instance=self.instance,
                character_id=character_id,
                character_name=str(character_id),
                role="squad_member",
                role_name="Squad Member",
                ship_type_id=ship_type_id,
                ship_name="",
                solar_system_id=1,
                solar_system_name="",
                squad_id=1,
                wing_id=wing_id,
            )

    def roles(self, character_id):
        return set(
            VoiceGrant.objects.filter(
                character_id=character_id, expires_at__isnull=True
            ).values_list("source", "role")
        )

    def test_in_game_members_logistics_and_wings(self):
        logi = _ship(11978, "Logistics")
        rifter = _ship(587, "Frigate")
        self.member(1001, logi, wing_id=7)
        self.member(1002, rifter, wing_id=8)
        changed = grants.sync_fleet(self.fleet_)
        self.assertTrue({1001, 1002} <= changed)
        logi_grant = VoiceGrant.objects.get(character_id=1001)
        self.assertTrue(logi_grant.logistics)
        self.assertEqual(logi_grant.wing_id, 7)
        self.assertFalse(VoiceGrant.objects.get(character_id=1002).logistics)
        # Running it again changes nothing.
        self.assertEqual(grants.sync_fleet(self.fleet_), set())

    def test_creator_and_boss_are_commanders(self):
        grants.sync_fleet(self.fleet_)
        self.assertEqual(
            self.roles(self.fc_char.character_id),
            {
                (VoiceGrant.SOURCE_CREATOR, VoiceGrant.ROLE_COMMANDER),
                (VoiceGrant.SOURCE_BOSS, VoiceGrant.ROLE_COMMANDER),
            },
        )

    def test_capital_hull_needs_a_trusted_pilot(self):
        dread = _ship(19720, "Dreadnought")
        user, member_char = self.pilot("cap member", "Alliance")
        self.member(member_char.character_id, dread)
        self.member(4242, dread)  # a neutral with no capital history
        grants.sync_fleet(self.fleet_)
        self.assertIn(
            (VoiceGrant.SOURCE_CAPITAL, VoiceGrant.ROLE_CAPITAL),
            self.roles(member_char.character_id),
        )
        self.assertNotIn(
            (VoiceGrant.SOURCE_CAPITAL, VoiceGrant.ROLE_CAPITAL),
            self.roles(4242),
        )
        del user

    def test_invites_said_in_except_low_confidence(self):
        sure_user, sure_char = self.pilot("sure", "Alliance")
        unsure_user, unsure_char = self.pilot("unsure", "Alliance")
        wave = EveFleetInviteWave.objects.create(
            eve_fleet=self.fleet_, number=1
        )
        for user, confidence in ((sure_user, ""), (unsure_user, "low")):
            EveFleetInvite.objects.create(
                eve_fleet=self.fleet_,
                wave=wave,
                user=user,
                answer=EveFleetInvite.ANSWER_IN,
                confidence=confidence,
            )
        grants.sync_fleet(self.fleet_)
        self.assertIn(
            (VoiceGrant.SOURCE_INVITE, VoiceGrant.ROLE_MEMBER),
            self.roles(sure_char.character_id),
        )
        self.assertEqual(self.roles(unsure_char.character_id), set())

    def test_an_alt_in_fleet_gives_the_grant_to_the_main(self):
        user, main = self.pilot("flies an alt", "Alliance")
        alt = self.alt(user, "the alt")
        self.member(alt.character_id, _ship(11978, "Logistics"), wing_id=4)
        grants.sync_fleet(self.fleet_)
        self.assertEqual(self.roles(alt.character_id), set())
        self.assertIn(
            (VoiceGrant.SOURCE_IN_FLEET, VoiceGrant.ROLE_MEMBER),
            self.roles(main.character_id),
        )
        grant = VoiceGrant.objects.get(
            character_id=main.character_id, source=VoiceGrant.SOURCE_IN_FLEET
        )
        self.assertTrue(grant.logistics)
        self.assertEqual(grant.wing_id, 4)

    def test_backing_out_ends_the_grant_but_not_a_co_fc(self):
        user, character = self.pilot("volunteer", "Alliance")
        volunteer = EveFleetRoleVolunteer.objects.create(
            eve_fleet=self.fleet_,
            character_id=character.character_id,
            character_name="volunteer",
            role="scout",
        )
        VoiceGrant.objects.create(
            character_id=character.character_id,
            fleet=self.fleet_,
            source=VoiceGrant.SOURCE_CO_FC,
            role=VoiceGrant.ROLE_COMMANDER,
        )
        grants.sync_fleet(self.fleet_)
        self.assertIn(
            (VoiceGrant.SOURCE_VOLUNTEER, VoiceGrant.ROLE_MEMBER),
            self.roles(character.character_id),
        )
        volunteer.delete()
        changed = grants.sync_fleet(self.fleet_)
        self.assertIn(character.character_id, changed)
        self.assertEqual(
            self.roles(character.character_id),
            {(VoiceGrant.SOURCE_CO_FC, VoiceGrant.ROLE_COMMANDER)},
        )
        del user

    def test_leaving_the_in_game_fleet_ends_the_grant(self):
        member = self.member(3010, _ship(587, "Frigate"))
        grants.sync_fleet(self.fleet_)
        self.assertTrue(self.roles(3010))
        member.delete()
        grants.sync_fleet(self.fleet_)
        self.assertEqual(self.roles(3010), set())

    def test_a_kick_lasts_for_the_lease(self):
        self.member(3003, _ship(587, "Frigate"))
        grants.sync_fleet(self.fleet_)
        VoiceGrant.objects.filter(character_id=3003).update(
            expires_at=timezone.now()
        )
        VoiceAuditEvent.record(
            VoiceAuditEvent.KIND_KICK,
            character_id=3003,
            fleet_id=self.fleet_.id,
        )
        grants.sync_fleet(self.fleet_)
        self.assertEqual(self.roles(3003), set())
