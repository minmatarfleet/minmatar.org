"""Fanfest becomes a Pulse group, and every member comes with it."""

from datetime import timedelta
from unittest.mock import Mock, patch

from django.apps import apps
from django.contrib.auth.models import Group, User
from django.db.models import signals as django_signals
from django.test import TestCase
from django.utils import timezone

from discord.exceptions import DiscordRoleAssignmentError
from discord.models import DiscordGuild, DiscordRole
from discord.signals import (
    group_post_save,
    resolve_existing_discord_role_from_server,
    user_group_changed,
)
from eveonline.models import EveCharacter, EvePlayer
from posts.models import EvePost
from tribes.helpers.move_fanfest_into_pulse import (
    NEW_CODE,
    NEW_GROUP_AUTH,
    OLD_CODE,
    PULSE_AUTH,
    TRIBE_AUTH,
    move_fanfest_into_pulse,
)
from tribes.models import (
    Tribe,
    TribeChiefVolunteer,
    TribeEvent,
    TribeGroup,
    TribeGroupChief,
    TribeGroupInvitation,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
    TribeGroupMembershipHistory,
    TribeGroupRank,
    TribeGroupRequirement,
)

ACTIVE = TribeGroupMembership.STATUS_ACTIVE
PENDING = TribeGroupMembership.STATUS_PENDING
INACTIVE = TribeGroupMembership.STATUS_INACTIVE


class MoveFanfestIntoPulseTestCase(TestCase):
    def setUp(self):
        self._restores = []
        pairs = (
            (
                django_signals.m2m_changed,
                user_group_changed,
                {
                    "sender": User.groups.through,
                    "dispatch_uid": "user_group_changed",
                },
            ),
            (
                django_signals.post_save,
                group_post_save,
                {"sender": Group, "dispatch_uid": "group_post_save"},
            ),
            (
                django_signals.pre_save,
                resolve_existing_discord_role_from_server,
                {
                    "sender": DiscordRole,
                    "dispatch_uid": "resolve_existing_discord_role_from_server",
                },
            ),
        )
        for signal, receiver, kwargs in pairs:
            if signal.disconnect(receiver, **kwargs):
                self._restores.append((signal, receiver, kwargs))
        self.addCleanup(self._restore_signals)
        public = patch("eveonline.signals.update_character_public_data")
        public.start()
        self.addCleanup(public.stop)
        role_delete = patch("discord.models.discord.delete_role")
        self.delete_role = role_delete.start()
        self.addCleanup(role_delete.stop)

        self.pulse_chief = User.objects.create(username="pulse-chief")
        self.fanfest_chief = User.objects.create(username="sycamoria")
        self.pulse_auth = Group.objects.create(name=PULSE_AUTH)
        self.fanfest_auth = Group.objects.create(name=TRIBE_AUTH)
        self.attendees_auth = Group.objects.create(
            name="Tribe Group - Fanfest Attendees"
        )
        self.pulse = Tribe.objects.create(
            name="Pulse",
            slug="pulse",
            group=self.pulse_auth,
            chief=self.pulse_chief,
        )
        self.fanfest = Tribe.objects.create(
            name="Fanfest",
            slug="fanfest",
            description=(
                "Flying out to EVE Fanfest? Meet the pilots going, plan "
                "the trip together, and represent the alliance."
            ),
            content="Pack a capsule.",
            discord_channel_id=4242,
            group=self.fanfest_auth,
            chief=self.fanfest_chief,
        )
        self.group = TribeGroup.objects.create(
            tribe=self.fanfest,
            name="Attendees",
            code=OLD_CODE,
            description="Pilots attending or helping organise EVE Fanfest.",
            group=self.attendees_auth,
            is_active=True,
        )

    def _restore_signals(self):
        for signal, receiver, kwargs in self._restores:
            signal.connect(receiver, **kwargs)

    def _move(self, discord_client=None):
        return move_fanfest_into_pulse(apps, discord_client=discord_client)

    def _user(self, username):
        return User.objects.create(username=username)

    def _membership(self, user, status, group=None):
        return TribeGroupMembership.objects.create(
            user=user,
            tribe_group=group or self.group,
            status=status,
            approved_at=timezone.now() if status == ACTIVE else None,
        )

    def test_reparents_group_and_keeps_people(self):
        active = self._user("active-pilot")
        pending = self._user("pending-pilot")
        inactive = self._user("inactive-pilot")
        other_pulse = self._user("already-pulse")
        active.groups.add(self.fanfest_auth, self.attendees_auth)
        pending.groups.add(self.fanfest_auth, self.attendees_auth)
        inactive.groups.add(self.fanfest_auth)
        other_pulse.groups.add(self.pulse_auth, self.fanfest_auth)
        active_row = self._membership(active, ACTIVE)
        pending_row = self._membership(pending, PENDING)
        inactive_row = self._membership(inactive, INACTIVE)
        readiness = TribeGroup.objects.create(
            tribe=self.pulse,
            name="Readiness",
            code="pulse.readiness",
        )
        self._membership(other_pulse, ACTIVE, readiness)
        character = EveCharacter.objects.create(
            character_id=9100101, character_name="Active Pilot", user=active
        )
        committed = TribeGroupMembershipCharacter.objects.create(
            membership=active_row, character=character
        )
        requirement = TribeGroupRequirement.objects.create(
            tribe_group=self.group
        )
        invitation = TribeGroupInvitation.objects.create(
            tribe_group=self.group,
            user=pending,
            status="pending",
            expires_at=timezone.now() + timedelta(days=3),
        )
        event = TribeEvent.objects.create(
            tribe_group=self.group,
            title="Meetup",
            starts_at=timezone.now() + timedelta(days=10),
        )
        rank_auth = Group.objects.create(name="Fanfest Marshal")
        TribeGroupRank.objects.create(
            tribe_group=self.group,
            name="Marshal",
            code="marshal",
            group=rank_auth,
        )
        inactive.groups.add(rank_auth)
        group_pk = self.group.pk

        self._move()

        group = TribeGroup.objects.get(pk=group_pk)
        self.assertEqual(group.tribe_id, self.pulse.pk)
        self.assertEqual(group.code, NEW_CODE)
        self.assertEqual(group.name, "Fanfest")
        self.assertEqual(
            TribeGroupChief.objects.get(
                tribe_group=group, region="US"
            ).user_id,
            self.fanfest_chief.pk,
        )
        self.assertEqual(group.discord_channel_id, 4242)
        self.assertEqual(group.content, "Pack a capsule.")
        self.assertIn("Meet the pilots going", group.description)
        self.assertEqual(group.group.name, NEW_GROUP_AUTH)
        self.assertEqual(
            Tribe.objects.get(pk=self.pulse.pk).chief_id, self.pulse_chief.pk
        )
        self.assertFalse(Tribe.objects.filter(slug="fanfest").exists())
        self.assertFalse(Group.objects.filter(name=TRIBE_AUTH).exists())

        active_row.refresh_from_db()
        pending_row.refresh_from_db()
        inactive_row.refresh_from_db()
        self.assertEqual(active_row.tribe_group_id, group_pk)
        self.assertEqual(active_row.status, ACTIVE)
        self.assertEqual(pending_row.status, PENDING)
        self.assertEqual(inactive_row.status, INACTIVE)
        self.assertTrue(
            TribeGroupMembershipCharacter.objects.filter(
                pk=committed.pk
            ).exists()
        )
        self.assertEqual(
            TribeGroupRequirement.objects.get(
                pk=requirement.pk
            ).tribe_group_id,
            group_pk,
        )
        self.assertEqual(
            TribeGroupInvitation.objects.get(pk=invitation.pk).tribe_group_id,
            group_pk,
        )
        self.assertEqual(
            TribeEvent.objects.get(pk=event.pk).tribe_group_id, group_pk
        )

        self.assertIn(self.pulse_auth, active.groups.all())
        self.assertIn(group.group, active.groups.all())
        self.assertNotIn(self.fanfest_auth, active.groups.all())
        self.assertFalse(pending.groups.filter(pk=self.pulse_auth.pk).exists())
        self.assertFalse(pending.groups.filter(pk=group.group_id).exists())
        self.assertFalse(
            inactive.groups.filter(pk=self.pulse_auth.pk).exists()
        )
        self.assertFalse(inactive.groups.filter(pk=rank_auth.pk).exists())
        self.assertIn(self.pulse_auth, other_pulse.groups.all())
        self.assertFalse(other_pulse.groups.filter(name=TRIBE_AUTH).exists())

    def test_keeps_a_custom_group_description_and_existing_group_chief(self):
        leader = self._user("group-leader")
        self.group.description = "Custom blurb"
        TribeGroupChief.objects.create(
            tribe_group=self.group, region="US", user=leader
        )
        self.group.discord_channel_id = 77
        self.group.save()

        self._move()

        group = TribeGroup.objects.get(pk=self.group.pk)
        self.assertEqual(group.description, "Custom blurb")
        self.assertEqual(
            list(group.chief_seats.values_list("user_id", flat=True)),
            [leader.pk],
        )
        self.assertEqual(group.discord_channel_id, 77)

    def test_reparents_other_fanfest_groups(self):
        helpers_auth = Group.objects.create(name="Tribe Group - Travel")
        helpers = TribeGroup.objects.create(
            tribe=self.fanfest,
            name="Travel",
            code="fanfest.travel",
            group=helpers_auth,
        )
        pilot = self._user("traveller")
        self._membership(pilot, ACTIVE, helpers)
        pilot.groups.add(self.fanfest_auth)

        self._move()

        helpers.refresh_from_db()
        self.assertEqual(helpers.tribe_id, self.pulse.pk)
        self.assertEqual(helpers.code, "pulse.travel")
        self.assertEqual(helpers.group_id, helpers_auth.pk)
        self.assertIn(self.pulse_auth, pilot.groups.all())
        self.assertTrue(
            TribeGroupMembership.objects.filter(
                user=pilot, tribe_group=helpers, status=ACTIVE
            ).exists()
        )

    def test_role_holder_without_a_membership_joins_with_primary_character(
        self,
    ):
        pilot = self._user("role-only")
        pilot.groups.add(self.fanfest_auth)
        character = EveCharacter.objects.create(
            character_id=9100102, character_name="Role Only", user=pilot
        )
        EvePlayer.objects.create(
            user=pilot, nickname="role-only", primary_character=character
        )

        self._move()

        membership = TribeGroupMembership.objects.get(user=pilot)
        self.assertEqual(membership.status, ACTIVE)
        self.assertEqual(membership.tribe_group.code, NEW_CODE)
        self.assertTrue(
            TribeGroupMembershipCharacter.objects.filter(
                membership=membership, character=character
            ).exists()
        )
        self.assertTrue(
            TribeGroupMembershipHistory.objects.filter(
                membership=membership, to_status=ACTIVE, reason="approved"
            ).exists()
        )
        self.assertIn(self.pulse_auth, pilot.groups.all())
        self.assertIn(membership.tribe_group.group, pilot.groups.all())

    def test_discord_failure_keeps_the_fanfest_role_for_a_retry(self):
        pilot = self._user("discord-down")
        pilot.groups.add(self.fanfest_auth, self.attendees_auth)
        row = self._membership(pilot, ACTIVE)

        def block_pulse(sender, instance, action, pk_set, **kwargs):
            del sender, kwargs
            if action == "pre_add" and self.pulse_auth.pk in (pk_set or set()):
                raise DiscordRoleAssignmentError("discord down")

        django_signals.m2m_changed.connect(
            block_pulse, sender=User.groups.through
        )
        self.addCleanup(
            django_signals.m2m_changed.disconnect,
            block_pulse,
            sender=User.groups.through,
        )
        self._move()
        django_signals.m2m_changed.disconnect(
            block_pulse, sender=User.groups.through
        )

        row.refresh_from_db()
        self.assertEqual(row.tribe_group.tribe_id, self.pulse.pk)
        self.assertEqual(row.status, ACTIVE)
        self.assertIn(self.fanfest_auth, pilot.groups.all())
        self.assertNotIn(self.pulse_auth, pilot.groups.all())
        self.assertTrue(Group.objects.filter(name=TRIBE_AUTH).exists())

        self._move()

        pilot.refresh_from_db()
        self.assertIn(self.pulse_auth, pilot.groups.all())
        self.assertFalse(pilot.groups.filter(name=TRIBE_AUTH).exists())
        self.assertEqual(
            TribeGroupMembership.objects.filter(user=pilot).count(), 1
        )

    def test_renames_the_discord_role_in_place(self):
        DiscordRole.objects.create(
            role_id=7001,
            name=self.attendees_auth.name,
            group=self.attendees_auth,
        )
        DiscordRole.objects.create(
            role_id=7002, name=TRIBE_AUTH, group=self.fanfest_auth
        )
        client = Mock()

        self._move(discord_client=client)

        role = DiscordRole.objects.get(role_id=7001)
        self.assertEqual(role.name, NEW_GROUP_AUTH)
        client.edit_role.assert_called_once_with(7001, NEW_GROUP_AUTH)
        self.delete_role.assert_called_once_with(7002)

    def test_leaves_fanfest_alone_when_pulse_is_missing(self):
        self.pulse.delete()

        lines = self._move()

        self.assertTrue(Tribe.objects.filter(slug="fanfest").exists())
        self.assertEqual(
            TribeGroup.objects.get(pk=self.group.pk).code, OLD_CODE
        )
        self.assertTrue(any("Pulse tribe missing" in line for line in lines))

    def test_deactivates_the_tribe_when_it_has_its_own_discord(self):
        guild = DiscordGuild.objects.create(
            guild_id=5150, name="Fanfest Discord"
        )
        self.fanfest.discord_guild = guild
        self.fanfest.save(update_fields=["discord_guild"])

        self._move()

        self.fanfest.refresh_from_db()
        self.assertFalse(self.fanfest.is_active)
        self.assertIsNone(self.fanfest.chief_id)
        self.assertEqual(self.fanfest.discord_guild_id, guild.pk)
        self.assertEqual(
            TribeGroup.objects.get(pk=self.group.pk).tribe_id, self.pulse.pk
        )

    def test_moves_chief_volunteers_onto_the_group_seat(self):
        self.fanfest.chief = None
        self.fanfest.save(update_fields=["chief"])
        offer = TribeChiefVolunteer.objects.create(
            tribe=self.fanfest, user=self._user("volunteer")
        )

        self._move()

        offer.refresh_from_db()
        self.assertEqual(offer.tribe_id, self.pulse.pk)
        self.assertEqual(offer.tribe_group_id, self.group.pk)
        self.assertEqual(offer.status, TribeChiefVolunteer.STATUS_PENDING)

    def test_closes_tribe_chief_offers_when_the_group_has_a_chief(self):
        offer = TribeChiefVolunteer.objects.create(
            tribe=self.fanfest, user=self._user("late-volunteer")
        )

        self._move()

        offer.refresh_from_db()
        self.assertEqual(offer.status, TribeChiefVolunteer.STATUS_CLOSED)
        self.assertEqual(offer.tribe_group_id, self.group.pk)
        self.assertEqual(
            TribeGroupChief.objects.get(
                tribe_group_id=self.group.pk, region="US"
            ).user_id,
            self.fanfest_chief.pk,
        )

    def test_merges_a_duplicate_attendees_group_into_pulse_fanfest(self):
        survivor_auth = Group.objects.create(name=NEW_GROUP_AUTH)
        survivor = TribeGroup.objects.create(
            tribe=self.pulse,
            name="Fanfest",
            code=NEW_CODE,
            group=survivor_auth,
        )
        kept = self._user("already-there")
        moved = self._user("moving-over")
        overlap = self._user("both")
        self._membership(kept, PENDING, survivor)
        self._membership(moved, ACTIVE)
        overlap_survivor = self._membership(overlap, PENDING, survivor)
        overlap_source = self._membership(overlap, ACTIVE)
        character = EveCharacter.objects.create(
            character_id=9100103, character_name="Both", user=overlap
        )
        TribeGroupMembershipCharacter.objects.create(
            membership=overlap_source, character=character
        )
        post = EvePost.objects.create(
            title="Fanfest plans",
            seo_description="plans",
            slug="fanfest-plans",
            content="See you there",
            user=moved,
            host_group=self.group,
        )
        moved.groups.add(self.attendees_auth, self.fanfest_auth)

        self._move()

        self.assertFalse(TribeGroup.objects.filter(code=OLD_CODE).exists())
        kept_row = TribeGroupMembership.objects.get(user=kept)
        moved_row = TribeGroupMembership.objects.get(user=moved)
        overlap_row = TribeGroupMembership.objects.get(user=overlap)
        self.assertEqual(kept_row.tribe_group_id, survivor.pk)
        self.assertEqual(kept_row.status, PENDING)
        self.assertEqual(moved_row.tribe_group_id, survivor.pk)
        self.assertEqual(moved_row.status, ACTIVE)
        self.assertEqual(overlap_row.pk, overlap_survivor.pk)
        self.assertEqual(overlap_row.status, ACTIVE)
        self.assertTrue(
            TribeGroupMembershipCharacter.objects.filter(
                membership=overlap_row, character=character
            ).exists()
        )
        post.refresh_from_db()
        self.assertEqual(post.host_group_id, survivor.pk)
        self.assertIn(self.pulse_auth, moved.groups.all())
        self.assertIn(survivor_auth, moved.groups.all())

    def test_second_run_changes_nothing(self):
        pilot = self._user("once")
        self._membership(pilot, ACTIVE)
        pilot.groups.add(self.fanfest_auth, self.attendees_auth)

        self._move()
        self._move()

        self.assertEqual(TribeGroup.objects.filter(code=NEW_CODE).count(), 1)
        self.assertEqual(
            TribeGroupMembership.objects.filter(user=pilot).count(), 1
        )

    def test_noop_when_fanfest_was_never_created(self):
        self.fanfest.delete()

        lines = self._move()

        self.assertTrue(any("nothing to move" in line for line in lines))
        self.assertFalse(TribeGroup.objects.filter(code=NEW_CODE).exists())
