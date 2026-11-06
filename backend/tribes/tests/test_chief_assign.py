"""Superusers swap a tribe or group chief from the site."""

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from audit.models import AuditEntry
from tribes.models import (
    Tribe,
    TribeChiefVolunteer,
    TribeGroup,
    TribeGroupMembership,
)
from tribes.tests.test_chief_volunteers import (  # noqa: F401  # pylint: disable=unused-import
    EXECUTOR_CHARACTER_ID,
    _auth,
    _pilot,
    setUpModule,
)

BASE_URL = "/api/tribes"


@override_settings(ALLIANCE_EXECUTOR_CHARACTER_ID=EXECUTOR_CHARACTER_ID)
class SetChiefTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        for target in ("tribes.tasks.discord",):
            patcher = patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.admin = _pilot("root", 91001, "Root Admin", 800)
        self.admin.is_superuser = True
        self.admin.save()
        self.old = _pilot("faye", 92001, "Faye Vaelent", 701)
        self.new = _pilot("casper", 92002, "Casper Sullivan", 702)
        self.tribe = Tribe.objects.create(
            name="Pulse", slug="pulse-assign", chief=self.old
        )
        self.group = TribeGroup.objects.create(
            tribe=self.tribe,
            name="Fishermen",
            code="pulse.fish-assign",
            chief=self.old,
        )

    def _put(self, url, user, who):
        return self.client.put(
            f"{BASE_URL}/{url}",
            data=json.dumps({"user_id": who.pk if who else None}),
            content_type="application/json",
            **_auth(user),
        )

    def test_flag_only_for_superusers(self):
        url = f"{BASE_URL}/{self.tribe.pk}"
        self.assertFalse(self.client.get(url).json()["can_set_chief"])
        self.assertFalse(
            self.client.get(url, **_auth(self.new)).json()["can_set_chief"]
        )
        self.assertTrue(
            self.client.get(url, **_auth(self.admin)).json()["can_set_chief"]
        )
        group_url = f"{url}/groups/{self.group.pk}"
        self.assertTrue(
            self.client.get(group_url, **_auth(self.admin)).json()[
                "can_set_chief"
            ]
        )
        self.assertFalse(self.client.get(group_url).json()["can_set_chief"])

    def test_plain_pilot_and_executor_are_refused(self):
        response = self._put(f"{self.tribe.pk}/chief", self.new, self.new)
        self.assertEqual(response.status_code, 403)
        self.tribe.refresh_from_db()
        self.assertEqual(self.tribe.chief, self.old)

    def test_superuser_swaps_a_group_chief(self):
        response = self._put(
            f"{self.tribe.pk}/groups/{self.group.pk}/chief",
            self.admin,
            self.new,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["character_name"], "Casper Sullivan")
        self.group.refresh_from_db()
        self.assertEqual(self.group.chief, self.new)
        membership = TribeGroupMembership.objects.get(
            user=self.new, tribe_group=self.group
        )
        self.assertEqual(membership.status, TribeGroupMembership.STATUS_ACTIVE)
        entry = AuditEntry.objects.get(user=self.admin)
        self.assertIn("Fishermen", entry.summary)
        self.assertIn("Faye Vaelent", entry.summary)
        self.assertIn("Casper Sullivan", entry.summary)

    def test_superuser_swaps_a_tribe_chief_and_closes_offers(self):
        offer = TribeChiefVolunteer.objects.create(
            tribe=self.tribe, user=self.new
        )
        response = self._put(f"{self.tribe.pk}/chief", self.admin, self.new)
        self.assertEqual(response.status_code, 200)
        self.tribe.refresh_from_db()
        self.assertEqual(self.tribe.chief, self.new)
        offer.refresh_from_db()
        self.assertEqual(offer.status, TribeChiefVolunteer.STATUS_CLOSED)
        self.assertTrue(
            TribeGroupMembership.objects.filter(
                user=self.new,
                tribe_group=self.group,
                status=TribeGroupMembership.STATUS_ACTIVE,
            ).exists()
        )

    def test_superuser_can_empty_a_seat(self):
        response = self._put(f"{self.tribe.pk}/chief", self.admin, None)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["user_id"])
        self.tribe.refresh_from_db()
        self.assertIsNone(self.tribe.chief)

    def test_same_chief_is_a_no_op(self):
        response = self._put(f"{self.tribe.pk}/chief", self.admin, self.old)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AuditEntry.objects.exists())

    def test_unknown_seat_or_pilot_is_404(self):
        self.assertEqual(
            self._put("999999/chief", self.admin, self.new).status_code, 404
        )
        self.assertEqual(
            self._put(
                f"{self.tribe.pk}/groups/999999/chief", self.admin, self.new
            ).status_code,
            404,
        )
        response = self.client.put(
            f"{BASE_URL}/{self.tribe.pk}/chief",
            data=json.dumps({"user_id": 999999}),
            content_type="application/json",
            **_auth(self.admin),
        )
        self.assertEqual(response.status_code, 404)

    def test_candidates_search(self):
        url = f"{BASE_URL}/chief-candidates"
        self.assertEqual(
            self.client.get(url, {"q": "cas"}, **_auth(self.new)).status_code,
            403,
        )
        response = self.client.get(url, {"q": "casper"}, **_auth(self.admin))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["user_id"] for row in response.json()], [self.new.pk]
        )
        self.assertEqual(
            self.client.get(url, {"q": "c"}, **_auth(self.admin)).json(), []
        )
        self.assertTrue(User.objects.filter(pk=self.new.pk).exists())
