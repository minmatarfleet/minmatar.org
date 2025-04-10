from django.test import Client

from app.test import TestCase
from standingfleet.models import StandingFleetVoiceRecord

BASE_URL = "/api/standingfleet"


class StandingFleetRouterTestCase(TestCase):
    """Test cases for the standing fleet router."""

    def setUp(self):
        # create test client
        self.client = Client()

        super().setUp()

    def test_voice_track(self):
        data = {"minutes": 7, "usernames": [self.user.username]}

        response = self.client.post(
            f"{BASE_URL}/voicetracking",
            data,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(200, response.status_code)
        ids = response.json()["ids"]
        self.assertEqual(1, len(ids))

        record = StandingFleetVoiceRecord.objects.get(id=ids[0])
        self.assertEqual(7, record.minutes)
