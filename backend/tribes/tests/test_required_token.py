"""Tests for TribeGroup.required_token_type gates and missing_token flags."""

import jwt
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models import signals as django_signals
from django.test import Client, TestCase
from esi.models import Token

from eveonline.models import EveCharacter
from eveonline.scopes import TokenType, add_scopes
from tribes.helpers.token_requirements import character_has_required_token
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
)

BASE_URL = "/api/tribes"


def _make_token(user: User) -> str:
    payload = {"user_id": user.pk}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def setUpModule():
    # pylint: disable-next=import-outside-toplevel
    from discord.signals import user_group_changed  # noqa: PLC0415

    django_signals.m2m_changed.disconnect(
        user_group_changed,
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
    )


def _attach_token(character: EveCharacter, user: User, token_type: TokenType):
    token = Token.objects.create(
        user=user,
        character_id=character.character_id,
        character_name=character.character_name,
    )
    add_scopes(token_type, token)
    character.token = token
    character.esi_token_level = token_type.value
    character.esi_scope_groups = [token_type.value]
    character.save()
    return token


class RequiredTokenHelperTestCase(TestCase):
    def setUp(self):
        self.tribe = Tribe.objects.create(name="Supply", slug="supply-tok")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe, name="Market", code="supply.market-tok"
        )
        self.user = User.objects.create_user(username="tok_helper")
        self.character = EveCharacter.objects.create(
            character_id=41001,
            character_name="Helper Pilot",
            user=self.user,
        )

    def test_blank_requirement_always_passes(self):
        self.assertTrue(
            character_has_required_token(self.character, self.group)
        )

    def test_missing_token_fails_when_required(self):
        self.group.required_token_type = TokenType.MARKET.value
        self.group.save()
        self.assertFalse(
            character_has_required_token(self.character, self.group)
        )

    def test_basic_token_fails_market_requirement(self):
        self.group.required_token_type = TokenType.MARKET.value
        self.group.save()
        _attach_token(self.character, self.user, TokenType.BASIC)
        self.assertFalse(
            character_has_required_token(self.character, self.group)
        )

    def test_market_token_satisfies_market_requirement(self):
        self.group.required_token_type = TokenType.MARKET.value
        self.group.save()
        _attach_token(self.character, self.user, TokenType.MARKET)
        self.assertTrue(
            character_has_required_token(self.character, self.group)
        )

    def test_suspended_token_fails(self):
        self.group.required_token_type = TokenType.MARKET.value
        self.group.save()
        _attach_token(self.character, self.user, TokenType.MARKET)
        self.character.esi_suspended = True
        self.character.save()
        self.assertFalse(
            character_has_required_token(self.character, self.group)
        )


class RequiredTokenGateTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Supply", slug="supply-gate")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Market",
            code="supply.market-gate",
            required_token_type=TokenType.MARKET.value,
        )
        self.user = User.objects.create_user(username="tok_gate")
        content_type = ContentType.objects.get(
            app_label="tribes", model="tribegroupmembership"
        )
        perm = Permission.objects.get(
            codename="add_tribegroupmembership", content_type=content_type
        )
        self.user.user_permissions.add(perm)
        self.auth = _make_token(self.user)
        self.character = EveCharacter.objects.create(
            character_id=42001,
            character_name="Gate Pilot",
            user=self.user,
        )
        self.apply_url = (
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}/memberships"
        )

    def test_group_schema_includes_required_token_type(self):
        response = self.client.get(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["required_token_type"], TokenType.MARKET.value
        )

    def test_blank_requirement_allows_apply_without_token(self):
        self.group.required_token_type = ""
        self.group.save()
        response = self.client.post(
            self.apply_url,
            data={"character_ids": [self.character.character_id]},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.auth}",
        )
        self.assertEqual(response.status_code, 200)

    def test_apply_blocked_without_market_token(self):
        _attach_token(self.character, self.user, TokenType.BASIC)
        response = self.client.post(
            self.apply_url,
            data={"character_ids": [self.character.character_id]},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.auth}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Market ESI token", response.json()["detail"])
        self.assertFalse(
            TribeGroupMembership.objects.filter(
                user=self.user, tribe_group=self.group
            ).exists()
        )

    def test_apply_allowed_with_market_token(self):
        _attach_token(self.character, self.user, TokenType.MARKET)
        response = self.client.post(
            self.apply_url,
            data={"character_ids": [self.character.character_id]},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.auth}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "pending")

    def test_add_character_blocked_without_required_token(self):
        membership = TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        _attach_token(self.character, self.user, TokenType.BASIC)
        url = (
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}"
            f"/memberships/{membership.pk}/characters"
        )
        response = self.client.post(
            url,
            data={"character_id": self.character.character_id},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.auth}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Market ESI token", response.json()["detail"])

    def test_add_character_allowed_with_required_token(self):
        membership = TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        _attach_token(self.character, self.user, TokenType.MARKET)
        url = (
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}"
            f"/memberships/{membership.pk}/characters"
        )
        response = self.client.post(
            url,
            data={"character_id": self.character.character_id},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.auth}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["missing_token"])


class RequiredTokenMissingFlagTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Supply", slug="supply-flag")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Market",
            code="supply.market-flag",
            required_token_type=TokenType.MARKET.value,
        )
        self.user = User.objects.create_user(username="tok_flag")
        self.auth = _make_token(self.user)
        self.character = EveCharacter.objects.create(
            character_id=43001,
            character_name="Flag Pilot",
            user=self.user,
        )
        _attach_token(self.character, self.user, TokenType.BASIC)
        self.membership = TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.group,
            status=TribeGroupMembership.STATUS_ACTIVE,
        )
        TribeGroupMembershipCharacter.objects.create(
            membership=self.membership,
            character=self.character,
        )

    def test_available_characters_reports_missing_token(self):
        url = (
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}"
            f"/memberships/characters-available"
        )
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.auth}"
        )
        self.assertEqual(response.status_code, 200)
        row = next(
            r
            for r in response.json()
            if r["character_id"] == self.character.character_id
        )
        self.assertTrue(row["missing_token"])

    def test_existing_membership_lists_missing_token(self):
        url = (
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}"
            f"/memberships?mine=true"
        )
        response = self.client.get(
            url, HTTP_AUTHORIZATION=f"Bearer {self.auth}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(len(data[0]["characters"]), 1)
        self.assertTrue(data[0]["characters"][0]["missing_token"])
