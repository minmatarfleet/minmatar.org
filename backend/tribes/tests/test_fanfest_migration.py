import importlib

import factory

from django.apps import apps
from django.contrib.auth.models import User
from django.db.models import signals as django_signals
from django.test import TestCase

from eveonline.models import EveCharacter
from tribes.models import Tribe, TribeGroup

migration = importlib.import_module(
    "tribes.migrations.0050_seed_fanfest_tribe"
)

MUTED = (
    django_signals.pre_save,
    django_signals.post_save,
    django_signals.m2m_changed,
)


@factory.django.mute_signals(*MUTED)
class FanfestTribeMigrationTestCase(TestCase):
    def setUp(self):
        # The migration skips seeding in tests; start from no tribe.
        TribeGroup.objects.filter(code=migration.GROUP_CODE).delete()
        Tribe.objects.filter(slug=migration.TRIBE_SLUG).delete()

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
