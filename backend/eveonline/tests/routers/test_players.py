from django.test import Client

from app.test import TestCase
from eveonline.models import EvePlayer
from eveonline.helpers.characters import user_player

BASE_URL = "/api/eveonline/players"


class PlayerRouterTestCase(TestCase):
    """Test cases for the player router."""

    def setUp(self):
        self.client = Client()

        super().setUp()

    def test_get_current_player(self):
        EvePlayer.objects.create(user=self.user, nickname="Player One")
        response = self.client.get(
            f"{BASE_URL}/current", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 200)

    def test_no_current_player(self):
        response = self.client.get(
            f"{BASE_URL}/current", HTTP_AUTHORIZATION=f"Bearer {self.token}"
        )
        self.assertEqual(response.status_code, 404)

    def test_unauthorised_current_player(self):
        response = self.client.get(
            f"{BASE_URL}/current",
        )
        self.assertEqual(response.status_code, 401)

    def test_update_current_player(self):
        EvePlayer.objects.create(user=self.user, nickname="Player One")
        response = self.client.patch(
            f"{BASE_URL}/current",
            {"nickname": "bob", "prime_time": "EU_US"},
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)

        player = user_player(self.user)
        self.assertEqual("bob", player.nickname)
        self.assertEqual("EU_US", player.prime_time)

    def test_update_no_current_player(self):
        response = self.client.patch(
            f"{BASE_URL}/current",
            {"nickname": "bob", "prime_time": "EU_US"},
            "application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 404)
