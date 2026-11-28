"""The pending-application reminder posted in a tribe group's channel."""

from django.contrib.auth.models import User
from django.test import TestCase

from tribes.helpers.invitations import members_page_url
from tribes.models import Tribe, TribeGroup, TribeGroupMembership
from tribes.tasks import _build_reminder_message


class ReminderMessageTestCase(TestCase):
    def test_links_to_the_group_members_page(self):
        tribe = Tribe.objects.create(name="Supply", slug="supply")
        group = TribeGroup.objects.create(tribe=tribe, name="Mining")
        applicant = User.objects.create_user(username="miner")
        membership = TribeGroupMembership.objects.create(
            user=applicant,
            tribe_group=group,
            status=TribeGroupMembership.STATUS_PENDING,
        )

        message = _build_reminder_message(group, [membership])

        self.assertIn("- miner → Mining", message)
        self.assertIn(members_page_url(group), message)
        self.assertNotIn("admin panel", message)
