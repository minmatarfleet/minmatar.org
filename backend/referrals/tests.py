from django.test import Client

from app.test import TestCase

BASE_URL = "/api/referrals"


class ReferralRouterTestCase(TestCase):
    """Test cases for the referral router."""

    def setUp(self):
        # create test client
        self.client = Client()

        super().setUp()

    def test_record_click(self):
        data = {
            "page": "test_page",
            "user_id": self.user.id,
            "client_ip": "192.168.0.1",
        }
        response = self.client.post(
            f"{BASE_URL}",
            data,
            content_type="application/json",
        )

        self.assertEqual(201, response.status_code)

        response = self.client.get(
            f"{BASE_URL}/stats",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        stats = response.json()
        self.assertEqual(1, len(stats))
        self.assertEqual("test_page", stats[0]["name"])
        self.assertEqual(1, stats[0]["referrals"])
