from app.test import TestCase

from django.contrib.auth.models import Group, User
from django.db.models import signals

from groups.models import Sig, SigRequest, Team, TeamRequest


class GroupSignalsTests(TestCase):
    """Test cases for the Group model signals"""

    def setUp(self):
        # disconnect signals

        signals.post_save.disconnect(
            sender=Group,
            dispatch_uid="group_post_save",
        )
        signals.m2m_changed.disconnect(
            sender=User.groups.through,
            dispatch_uid="user_group_changed",
        )

        super().setUp()

    def test_sig_request_save_signal(self):

        group = Group.objects.create(
            name="Test SIG Group",
        )
        sig = Sig.objects.create(
            name="Test SIG",
            group=group,
        )

        self.assertEqual(0, sig.members.count())

        SigRequest.objects.create(
            user=self.user,
            sig=sig,
            approved=True,
        )

        self.assertEqual(1, sig.members.count())

    def test_team_request_save_signal(self):

        group = Group.objects.create(
            name="Test SIG Group",
        )
        team = Team.objects.create(
            name="Test Team",
            group=group,
        )

        self.assertEqual(0, team.members.count())

        TeamRequest.objects.create(
            user=self.user,
            team=team,
            approved=True,
        )

        self.assertEqual(1, team.members.count())
