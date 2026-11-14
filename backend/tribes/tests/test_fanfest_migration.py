import importlib
from unittest.mock import Mock, patch

from django.apps import apps
from django.contrib.auth.models import Group, User
from django.db.models import signals as django_signals
from django.test import TestCase

from discord.models import DiscordRole
from discord.signals import group_post_save
from eveonline.models import EveCharacter
from tribes.models import Tribe, TribeGroup

migration = importlib.import_module(
    "tribes.migrations.0050_seed_fanfest_tribe"
)


class FanfestTribeMigrationTestCase(TestCase):
    def setUp(self):
        public_data = patch("eveonline.signals.update_character_public_data")
        public_data.start()
        self.addCleanup(public_data.stop)
        # The migration skips seeding in tests; start from no tribe.
        TribeGroup.objects.filter(code=migration.GROUP_CODE).delete()
        Tribe.objects.filter(slug=migration.TRIBE_SLUG).delete()

    def _connect_group_signal(self):
        """Other test modules disconnect group_post_save process-wide."""
        kwargs = {"sender": Group, "dispatch_uid": "group_post_save"}
        was_connected = django_signals.post_save.disconnect(**kwargs)
        django_signals.post_save.connect(group_post_save, **kwargs)
        if not was_connected:
            self.addCleanup(django_signals.post_save.disconnect, **kwargs)

    def _character(self, name, character_id, user):
        return EveCharacter.objects.create(
            character_id=character_id, character_name=name, user=user
        )

    def test_creates_tribe_and_group_without_chief_when_pilot_missing(self):
        migration.seed_fanfest_tribe(apps)

        tribe = Tribe.objects.get(slug="fanfest")
        self.assertIsNone(tribe.chief_id)
        self.assertTrue(tribe.is_active)
        self.assertTrue(
            TribeGroup.objects.filter(
                tribe=tribe, code="fanfest.attendees"
            ).exists()
        )

    def test_sets_chief_from_character_name(self):
        user = User.objects.create(username="fan-chief")
        self._character("Sycamoria", 9100001, user)

        migration.seed_fanfest_tribe(apps)

        self.assertEqual(Tribe.objects.get(slug="fanfest").chief_id, user.pk)

    def test_ambiguous_name_leaves_chief_empty(self):
        user_a = User.objects.create(username="a")
        user_b = User.objects.create(username="b")
        self._character("Sycamoria", 9100002, user_a)
        self._character("sycamoria", 9100003, user_b)

        migration.seed_fanfest_tribe(apps)

        self.assertIsNone(Tribe.objects.get(slug="fanfest").chief_id)

    def test_is_idempotent_and_fills_empty_chief_only(self):
        migration.seed_fanfest_tribe(apps)
        migration.seed_fanfest_tribe(apps)
        self.assertEqual(Tribe.objects.filter(slug="fanfest").count(), 1)
        self.assertEqual(
            TribeGroup.objects.filter(code="fanfest.attendees").count(), 1
        )

        user = User.objects.create(username="late-chief")
        self._character("Sycamoria", 9100004, user)
        migration.seed_fanfest_tribe(apps)
        self.assertEqual(Tribe.objects.get(slug="fanfest").chief_id, user.pk)

        other = User.objects.create(username="other")
        Tribe.objects.filter(slug="fanfest").update(chief=other)
        migration.seed_fanfest_tribe(apps)
        self.assertEqual(Tribe.objects.get(slug="fanfest").chief_id, other.pk)

    def test_links_auth_groups_and_creates_discord_roles(self):
        self._connect_group_signal()
        with patch("discord.signals.discord") as client:
            client.get_roles.return_value = []
            client.create_role.side_effect = [
                Mock(json=Mock(return_value={"id": 7001})),
                Mock(json=Mock(return_value={"id": 7002})),
            ]
            migration.seed_fanfest_tribe(
                apps, auth_group_id=migration.ensure_auth_group_id
            )

        tribe = Tribe.objects.get(slug="fanfest")
        group = TribeGroup.objects.get(code="fanfest.attendees")
        self.assertEqual(tribe.group.name, "Tribe - Fanfest")
        self.assertEqual(group.group.name, "Tribe Group - Fanfest Attendees")
        self.assertEqual(
            {7001, 7002},
            set(
                DiscordRole.objects.filter(
                    group__in=[tribe.group, group.group]
                ).values_list("role_id", flat=True)
            ),
        )

    def test_discord_failure_leaves_groups_unlinked(self):
        self._connect_group_signal()
        with patch("discord.signals.discord") as client:
            client.get_roles.side_effect = RuntimeError("discord down")
            migration.seed_fanfest_tribe(
                apps, auth_group_id=migration.ensure_auth_group_id
            )

        self.assertIsNone(Tribe.objects.get(slug="fanfest").group_id)
        self.assertIsNone(
            TribeGroup.objects.get(code="fanfest.attendees").group_id
        )
        self.assertFalse(Group.objects.filter(name="Tribe - Fanfest").exists())
