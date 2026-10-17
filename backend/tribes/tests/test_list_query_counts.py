"""Roster and membership lists must not look up each member's main
one query at a time."""

import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext

from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter
from tribes.models import Tribe, TribeGroup, TribeGroupMembership

BASE_URL = "/api/tribes"


def _bearer(user: User) -> str:
    token = jwt.encode({"user_id": user.pk}, settings.SECRET_KEY, "HS256")
    return f"Bearer {token}"


class TribeListQueryCountTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.tribe = Tribe.objects.create(name="Supply", slug="supply")
        self.group = TribeGroup.objects.create(
            tribe=self.tribe, name="Mining", roster_hidden=True
        )
        self.chief = User.objects.create_user(username="chief")
        self.group.chief = self.chief
        self.group.save()
        self.members = 0

    def add_members(self, count: int):
        for _ in range(count):
            i = self.members
            self.members += 1
            user = User.objects.create_user(username=f"m{i}")
            char = EveCharacter.objects.create(
                character_id=50000 + i,
                character_name=f"Member {i}",
                user=user,
                corporation_id=98000001,
            )
            set_primary_character(user, char)
            TribeGroupMembership.objects.create(
                user=user,
                tribe_group=self.group,
                status=TribeGroupMembership.STATUS_ACTIVE,
            )

    def count_queries(self, url: str) -> tuple[int, list]:
        # Warm per-process caches (feature gates) so only the list counts.
        self.client.get(url, HTTP_AUTHORIZATION=_bearer(self.chief))
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(
                url, HTTP_AUTHORIZATION=_bearer(self.chief)
            )
        self.assertEqual(response.status_code, 200)
        return len(ctx.captured_queries), response.json()

    def assert_constant(self, url: str):
        self.add_members(2)
        few, body = self.count_queries(url)
        self.assertEqual(len(body), 2)
        self.add_members(4)
        many, body = self.count_queries(url)
        self.assertEqual(len(body), 6)
        self.assertEqual(few, many)
        return body

    def test_roster_queries_do_not_grow_with_members(self):
        body = self.assert_constant(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}/roster"
        )
        self.assertEqual(
            sorted(row["primary_character_name"] for row in body),
            [f"Member {i}" for i in range(6)],
        )

    def test_membership_list_queries_do_not_grow_with_members(self):
        body = self.assert_constant(
            f"{BASE_URL}/{self.tribe.pk}/groups/{self.group.pk}/memberships"
        )
        self.assertEqual(
            sorted(row["primary_character_name"] for row in body),
            [f"Member {i}" for i in range(6)],
        )
