from unittest.mock import patch

from django.contrib.auth.models import User
from django.db.models import signals
from django.test import Client

from app.test import TestCase
from app.testing import make_token
from eveonline.models import EveCharacter, EveCorporation

URL = "/api/eveonline/corporations/corporations/98726134/refresh"
TASK = (
    "eveonline.endpoints.corporations.post_corporation_refresh"
    ".update_corporation"
)


class CorporationRefreshTestCase(TestCase):
    def setUp(self):
        super().setUp()
        for uid in (
            "populate_eve_character_public_data",
            "populate_eve_character_private_data",
        ):
            signals.post_save.disconnect(sender=EveCharacter, dispatch_uid=uid)
        self.client = Client()
        ceo = EveCharacter.objects.create(
            character_id=2001, character_name="Ceo", user=self.user
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=98726134, name="Rattini Tribe", ceo=ceo
        )
        self.director_user = User.objects.create(username="director")
        director = EveCharacter.objects.create(
            character_id=2002,
            character_name="Director",
            user=self.director_user,
        )
        self.corporation.directors.add(director)
        self.member_user = User.objects.create(username="member")

    def post(self, user, url=URL):
        return self.client.post(
            url, HTTP_AUTHORIZATION=f"Bearer {make_token(user)}"
        )

    @patch(TASK)
    def test_ceo_queues_a_refresh(self, task):
        response = self.post(self.user)
        self.assertEqual(200, response.status_code)
        self.assertEqual({"queued": True}, response.json())
        task.apply_async.assert_called_once_with(args=[98726134])

    @patch(TASK)
    def test_director_queues_a_refresh(self, task):
        self.assertEqual(200, self.post(self.director_user).status_code)
        task.apply_async.assert_called_once_with(args=[98726134])

    @patch(TASK)
    def test_other_pilots_are_refused(self, task):
        response = self.post(self.member_user)
        self.assertEqual(403, response.status_code)
        task.apply_async.assert_not_called()

    @patch(TASK)
    def test_unknown_corporation_is_404(self, task):
        response = self.post(
            self.user,
            url="/api/eveonline/corporations/corporations/1/refresh",
        )
        self.assertEqual(404, response.status_code)
        task.apply_async.assert_not_called()

    def test_needs_a_signed_in_pilot(self):
        self.assertEqual(401, self.client.post(URL).status_code)
