from django.test import Client
from django.contrib.auth.models import Group

from app.test import TestCase

from groups.models import Sig

BASE_URL = "/api/sigs"


class SigsRouterTestCase(TestCase):
    """Django unit tests for the SIGs router"""

    def setUp(self):
        self.client = Client()

        super().setUp()

    def make_sig(self, name: str) -> Sig:
        group = Group.objects.create(name=name)
        return Sig.objects.create(name=name, group=group)

    def test_get_sigs(self):
        sig = self.make_sig("Test SIG")
        sig.members.add(self.user)
        self.make_sig("Another SIG")

        response = self.client.get(f"{BASE_URL}/")

        self.assertEqual(200, response.status_code)
        sigs = response.json()
        self.assertEqual(2, len(sigs))
        self.assertEqual("Test SIG", sigs[0]["name"])
        self.assertEqual("Another SIG", sigs[1]["name"])

        response = self.client.get(
            f"{BASE_URL}/current",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        sigs = response.json()
        self.assertEqual(1, len(sigs))
        self.assertEqual("Test SIG", sigs[0]["name"])

        response = self.client.get(f"{BASE_URL}/{sig.id}")
        self.assertEqual(200, response.status_code)
        sig = response.json()
        self.assertEqual("Test SIG", sig["name"])
