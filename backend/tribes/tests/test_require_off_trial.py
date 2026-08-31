"""Tests for TribeGroup.require_off_trial application gate."""

import jwt
from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models import signals as django_signals
from django.test import Client, TestCase
from esi.models import Token

from eveonline.models import EveCharacter
from eveonline.scopes import TokenType, add_scopes
from groups.models import UserCommunityStatus
from tribes.helpers.trial_requirements import (
    OFF_TRIAL_REQUIRED_DETAIL,
    application_blocked_by_trial,
)
from tribes.models import Tribe, TribeGroup

BASE_URL = "/api/tribes"


def _make_token(user: User) -> str:
    payload = {"user_id": user.pk}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def setUpModule():
    # pylint: disable-next=import-outside-toplevel
    from discord.signals import (  # noqa: PLC0415
        group_post_save,
        user_group_changed,
    )

    django_signals.m2m_changed.disconnect(
        user_group_changed,
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
    )
    django_signals.post_save.disconnect(
        group_post_save,
        sender=Group,
        dispatch_uid="group_post_save",
    )


class OffTrialHelperTestCase(TestCase):
    def setUp(self):
        self.tribe = Tribe.objects.create(name="Supply", slug="supply-trial")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Mining",
            code="supply.mining-trial",
            require_off_trial=True,
        )
        self.user = User.objects.create_user(username="trial_helper")

    def test_not_blocked_when_flag_off(self):
        self.group.require_off_trial = False
        self.group.save()
        UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_TRIAL
        )
        self.assertFalse(application_blocked_by_trial(self.user, self.group))

    def test_blocked_when_on_trial(self):
        UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_TRIAL
        )
        self.assertTrue(application_blocked_by_trial(self.user, self.group))

    def test_not_blocked_when_active(self):
        UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_ACTIVE
        )
        self.assertFalse(application_blocked_by_trial(self.user, self.group))


class OffTrialGateTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Supply", slug="supply-ot-gate")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Mining",
            code="supply.mining-ot-gate",
            require_off_trial=True,
        )
        self.user = User.objects.create_user(username="ot_gate")
        content_type = ContentType.objects.get(
            app_label="tribes", model="tribegroupmembership"
        )
        perm = Permission.objects.get(
            codename="add_tribegroupmembership", content_type=content_type
        )
        self.user.user_permissions.add(perm)
        self.character = EveCharacter.objects.create(
            character_id=52001,
            character_name="OT Pilot",
            user=self.user,
        )
        token = Token.objects.create(
            user=self.user,
            character_id=self.character.character_id,
            character_name=self.character.character_name,
        )
        add_scopes(TokenType.BASIC, token)
        self.character.token = token
        self.character.save()

    def test_schema_includes_require_off_trial(self):
        response = self.client.get(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["require_off_trial"])

    def test_apply_rejected_while_on_trial(self):
        UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_TRIAL
        )
        token = _make_token(self.user)
        response = self.client.post(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}/memberships",
            data={"character_ids": [self.character.character_id]},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], OFF_TRIAL_REQUIRED_DETAIL)

    def test_apply_allowed_when_active(self):
        UserCommunityStatus.objects.create(
            user=self.user, status=UserCommunityStatus.STATUS_ACTIVE
        )
        token = _make_token(self.user)
        response = self.client.post(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}/memberships",
            data={"character_ids": [self.character.character_id]},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
