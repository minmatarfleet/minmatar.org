"""Tests for tribe group hub endpoints (roster, growth, showcase)."""

import jwt
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db.models import signals as django_signals
from django.test import Client, TestCase
from django.utils import timezone

from eveonline.models import EveCharacter
from eveonline.models.characters import EvePlayer
from eveonline.models.corporations import EveCorporation
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipHistory,
    TribeGroupRank,
)

BASE_URL = "/api/tribes"


def _make_token(user: User) -> str:
    payload = {"user_id": user.pk}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def setUpModule():
    # pylint: disable-next=import-outside-toplevel
    from discord.signals import user_group_changed

    django_signals.m2m_changed.disconnect(
        user_group_changed,
        sender=User.groups.through,
        dispatch_uid="user_group_changed",
    )


def _grant_alliance_perm(user: User) -> None:
    content_type = ContentType.objects.get(
        app_label="eveonline", model="evecharactertag"
    )
    perm, _ = Permission.objects.get_or_create(
        codename="add_evecharactertag",
        content_type=content_type,
        defaults={"name": "Can add eve character tag"},
    )
    user.user_permissions.add(perm)


class TribeGroupRosterTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Capitals", slug="capitals")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe, name="Dreads", code="capitals.dreads"
        )
        self.member = User.objects.create_user(username="member")
        self.alliance = User.objects.create_user(username="alliance")
        _grant_alliance_perm(self.alliance)
        EveCorporation.objects.create(
            corporation_id=98000001,
            name="Minmatar Fleet Academy",
        )
        EveCharacter.objects.create(
            character_id=1001,
            character_name="Dread Main",
            user=self.member,
            corporation_id=98000001,
        )
        EvePlayer.objects.create(
            user=self.member,
            nickname="member-player",
            primary_character=EveCharacter.objects.get(character_id=1001),
        )
        membership = TribeGroupMembership.objects.create(
            user=self.member,
            tribe_group=self.group,
            status=TribeGroupMembership.STATUS_ACTIVE,
            approved_at=timezone.now(),
        )
        TribeGroupMembershipHistory.objects.create(
            membership=membership,
            from_status="",
            to_status=TribeGroupMembership.STATUS_ACTIVE,
            changed_by=self.alliance,
            reason="approved",
        )
        self.rank = TribeGroupRank.objects.create(
            tribe_group=self.group, name="Pilot", code="pilot", sort_order=1
        )
        membership.rank = self.rank
        membership.save(update_fields=["rank"])

    def test_guest_forbidden(self):
        response = self.client.get(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}/roster"
        )
        self.assertEqual(response.status_code, 401)

    def test_non_alliance_forbidden(self):
        token = _make_token(self.member)
        response = self.client.get(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}/roster",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 403)

    def test_alliance_sees_primary_only(self):
        token = _make_token(self.alliance)
        response = self.client.get(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}/roster",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["primary_character_name"], "Dread Main")
        self.assertEqual(data[0]["corporation_id"], 98000001)
        self.assertEqual(data[0]["corporation_name"], "Minmatar Fleet Academy")
        self.assertEqual(data[0]["rank_code"], "pilot")
        self.assertEqual(data[0]["rank_sort_order"], 1)
        self.assertNotIn("characters", data[0])


class TribeGroupGrowthTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Supply", slug="supply")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe, name="Mining", code="supply.mining"
        )
        self.user = User.objects.create_user(username="miner")
        membership = TribeGroupMembership.objects.create(
            user=self.user,
            tribe_group=self.group,
            status=TribeGroupMembership.STATUS_PENDING,
        )
        # Force a historical active interval that covers completed months.
        past = timezone.now() - timedelta(days=90)
        TribeGroupMembershipHistory.objects.filter(
            membership=membership
        ).delete()
        TribeGroupMembershipHistory.objects.create(
            membership=membership,
            from_status=TribeGroupMembership.STATUS_PENDING,
            to_status=TribeGroupMembership.STATUS_ACTIVE,
            changed_at=past,
            reason="approved",
        )
        TribeGroupMembership.objects.filter(pk=membership.pk).update(
            status=TribeGroupMembership.STATUS_ACTIVE,
            approved_at=past,
        )

    def test_growth_public(self):
        response = self.client.get(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}/growth"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("months", data)
        self.assertIn("counts", data)
        self.assertEqual(len(data["months"]), len(data["counts"]))
        self.assertTrue(any(c > 0 for c in data["counts"]))


class TribeGroupShowcaseTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Pulse", slug="pulse")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Thinkspeak",
            code="pulse.thinkspeak",
        )
        self.alliance = User.objects.create_user(username="ally")
        _grant_alliance_perm(self.alliance)

    def test_guest_gets_totals_without_names(self):
        response = self.client.get(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}/showcase"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["manual"])
        self.assertEqual(data["contributors"], [])

    def test_alliance_manual_still_empty_contributors(self):
        token = _make_token(self.alliance)
        response = self.client.get(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}/showcase",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["manual"])
        self.assertEqual(data["contributors"], [])
