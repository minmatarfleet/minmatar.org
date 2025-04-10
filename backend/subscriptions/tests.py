from django.test import Client

from app.test import TestCase

BASE_URL = "/api/subscriptions/"


class SubscriptionRouterTestCase(TestCase):
    """Test cases for the subscriptions router."""

    def setUp(self):
        # create test client
        self.client = Client()

        super().setUp()

    def test_subscriptions(self):
        response = self.client.get(
            f"{BASE_URL}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(response.json()))

        data = {"id": 1, "user_id": self.user.id, "subscription": "sub_1"}

        response = self.client.post(
            f"{BASE_URL}",
            data=data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(201, response.status_code)

        response = self.client.get(
            f"{BASE_URL}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(200, response.status_code)
        subs = response.json()
        self.assertEqual(1, len(subs))
        self.assertEqual("sub_1", subs[0]["subscription"])
