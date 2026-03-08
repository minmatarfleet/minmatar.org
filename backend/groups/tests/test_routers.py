from django.contrib.auth.models import Group, User
from django.db.models import signals
from django.test import Client

from app.test import TestCase
from discord.signals import user_group_changed
from groups.helpers import user_in_group_named


class GroupsRouterTestCase(TestCase):
    """Tests for groups helpers (tribe/group permission checks)."""

    def setUp(self):
        self.client = Client()
        super().setUp()

    def test_user_in_group_named(self):
        """user_in_group_named returns True when user is in the named auth group."""
        self.assertFalse(user_in_group_named(self.user, "Nonexistent Group"))

        signals.m2m_changed.disconnect(
            sender=User.groups.through,
            dispatch_uid="user_group_changed",
        )
        try:
            group = Group.objects.create(name="Test Group")
            self.user.groups.add(group)
            self.assertTrue(user_in_group_named(self.user, "Test Group"))
        finally:
            signals.m2m_changed.connect(
                user_group_changed,
                sender=User.groups.through,
                dispatch_uid="user_group_changed",
            )
