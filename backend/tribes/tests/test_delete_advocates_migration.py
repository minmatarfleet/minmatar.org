import importlib

import factory

from django.apps import apps
from django.contrib.auth.models import Group
from django.db.models import signals as django_signals
from django.test import TestCase

from tribes.models import Tribe, TribeGroup

migration = importlib.import_module(
    "tribes.migrations.0048_delete_advocates_tribe_group"
)


MUTED = (
    django_signals.pre_save,
    django_signals.post_save,
    django_signals.pre_delete,
    django_signals.post_delete,
    django_signals.m2m_changed,
)


class DeleteAdvocatesMigrationTestCase(TestCase):
    @factory.django.mute_signals(*MUTED)
    def test_removes_advocates_and_its_auth_group_only(self):
        tribe = Tribe.objects.create(name="Pulse", slug="pulse")
        advocates_group = Group.objects.create(name="Tribe Group - Advocates")
        other_group = Group.objects.create(name="Tribe Group - Readiness")
        TribeGroup.objects.create(
            tribe=tribe,
            name="Advocates",
            code="pulse.advocates",
            group=advocates_group,
        )
        TribeGroup.objects.create(
            tribe=tribe,
            name="Readiness",
            code="pulse.readiness",
            group=other_group,
        )

        migration.delete_advocates(apps, None)

        self.assertFalse(
            TribeGroup.objects.filter(code="pulse.advocates").exists()
        )
        self.assertFalse(Group.objects.filter(pk=advocates_group.pk).exists())
        self.assertTrue(
            TribeGroup.objects.filter(code="pulse.readiness").exists()
        )
        self.assertTrue(Group.objects.filter(pk=other_group.pk).exists())

    def test_noop_when_already_gone(self):
        migration.delete_advocates(apps, None)
