from app.test import TestCase

from django.contrib.auth.models import Group, User
from django.db.models import signals

from groups.helpers import sync_user_community_groups


class GroupSignalsTests(TestCase):
    """Test cases for groups signals (affiliation, community status)."""

    def setUp(self):
        signals.post_save.disconnect(
            sender=Group,
            dispatch_uid="group_post_save",
        )
        signals.m2m_changed.disconnect(
            sender=User.groups.through,
            dispatch_uid="user_group_changed",
        )
        super().setUp()

    def test_sync_user_community_groups_callable(self):
        """sync_user_community_groups can be called without error for user with no affiliation."""
        sync_user_community_groups(self.user)
