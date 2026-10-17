from django.test import Client, override_settings

from app.test import TestCase
from referrals.models import ReferralClick

BASE_URL = "/api/referrals"
SECRET = "frontend-secret"


@override_settings(SHARED_SECRET=SECRET)
class ReferralRouterTestCase(TestCase):
    """Test cases for the referral router."""

    def setUp(self):
        # create test client
        self.client = Client()

        super().setUp()

    def record(self, **headers):
        data = {
            "page": "test_page",
            "user_id": self.user.id,
            "client_ip": "192.168.0.1",
        }
        return self.client.post(
            f"{BASE_URL}",
            data,
            content_type="application/json",
            headers=headers,
        )

    def test_record_click(self):
        response = self.record(**{"X-Shared-Secret": SECRET})

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

    def test_record_click_requires_frontend_secret(self):
        for headers in ({}, {"X-Shared-Secret": "wrong"}):
            response = self.record(**headers)
            self.assertEqual(403, response.status_code)

        response = self.record(Authorization=f"Bearer {self.token}")
        self.assertEqual(403, response.status_code)
        self.assertFalse(ReferralClick.objects.exists())

    @override_settings(SHARED_SECRET="")
    def test_record_click_refused_when_secret_unset(self):
        response = self.record(**{"X-Shared-Secret": ""})
        self.assertEqual(403, response.status_code)
        self.assertFalse(ReferralClick.objects.exists())

    @override_settings(WEB_LINK_URL="https://my.minmatar.org")
    def test_redirect_targets_in_production(self):
        response = self.client.get(f"{BASE_URL}?page=corps&code=Q90")
        self.assertEqual(302, response.status_code)
        self.assertEqual(
            "https://my.minmatar.org/alliance/corporations/list/",
            response["Location"],
        )
        response = self.client.get(f"{BASE_URL}?page=nope&code=Q90")
        self.assertEqual(
            "https://my.minmatar.org/badreferral", response["Location"]
        )

    @override_settings(WEB_LINK_URL="http://localhost:4321")
    def test_redirect_targets_follow_web_link_url(self):
        response = self.client.get(f"{BASE_URL}?page=Freight&code=Q90")
        self.assertEqual(
            "http://localhost:4321/market/freight/standard/",
            response["Location"],
        )
        response = self.client.get(
            f"{BASE_URL}/links",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(
            {
                "http://localhost:4321/alliance/corporations/list/",
                "http://localhost:4321/market/freight/standard/",
                "http://localhost:4321/learning/guides/"
                "faction-warfare-plexing/",
                "http://localhost:4321/learning/guides/"
                "faction-warfare-advantage/",
            },
            {link["target"] for link in response.json()},
        )
