from django.test import Client

from app.test import TestCase

from eveonline.models import EvePlayer, EveCharacter
from eveonline.tests.routers.test_characters import (
    disconnect_character_signals,
)

from mumble.models import MumbleAccess
from mumble.tasks import set_mumble_usernames

BASE_URL = "/api/mumble"


class MumbleAccessTestCase(TestCase):
    """
    Unit tests for Mumble access
    """

    def setUp(self):
        # create test client
        self.client = Client()

        disconnect_character_signals()

        super().setUp()

    def test_mumble_access(self):
        self.make_superuser()

        EvePlayer.objects.create(
            user=self.user,
            primary_character=EveCharacter.objects.create(
                character_id=1234,
                character_name="Mr FC",
            ),
        )

        MumbleAccess.objects.create(
            user=self.user,
        )

        response = self.client.get(
            f"{BASE_URL}/connection",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        details = response.json()
        self.assertEqual("[FLEET] Mr FC", details["username"])
        password = details["password"]
        self.assertGreater(len(password), 10)

    def test_mumble_no_primary(self):
        self.make_superuser()

        MumbleAccess.objects.create(
            user=self.user,
        )

        response = self.client.get(
            f"{BASE_URL}/connection",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(404, response.status_code)

    def test_mumble_not_authorised(self):
        MumbleAccess.objects.create(
            user=self.user,
        )

        response = self.client.get(
            f"{BASE_URL}/connection",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(403, response.status_code)

    def test_mumble_suspended(self):
        self.make_superuser()

        EvePlayer.objects.create(
            user=self.user,
            primary_character=EveCharacter.objects.create(
                character_id=1234,
                character_name="Mr FC",
            ),
        )

        MumbleAccess.objects.create(
            user=self.user,
            suspended=True,
        )

        response = self.client.get(
            f"{BASE_URL}/connection",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(400, response.status_code)

    def test_update_name_task(self):
        EvePlayer.objects.create(
            user=self.user,
            primary_character=EveCharacter.objects.create(
                character_id=1234,
                character_name="Mr FC",
            ),
        )

        mumble_user = MumbleAccess.objects.create(
            user=self.user,
        )

        self.assertEqual(None, mumble_user.username)

        set_mumble_usernames()

        mumble_user = MumbleAccess.objects.filter(user=self.user).first()

        self.assertEqual("[FLEET] Mr FC", mumble_user.username)
