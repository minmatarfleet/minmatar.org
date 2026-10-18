from datetime import timedelta

from django.utils import timezone

from alliance.models import AllianceHealthSnapshot
from app.test import TestCase
from surveys.helpers.giveback import _community_snapshot


class GivebackCommunityTestCase(TestCase):
    def test_no_snapshot_leaves_active_pilots_unknown(self):
        self.assertEqual(_community_snapshot(), {"active_pilots": None})

    def test_active_pilots_come_from_the_latest_health_snapshot(self):
        now = timezone.now()
        AllianceHealthSnapshot.objects.create(
            computed_at=now - timedelta(hours=1), payload={"map_30d": 40}
        )
        AllianceHealthSnapshot.objects.create(
            computed_at=now, payload={"map_30d": 42}
        )
        self.assertEqual(_community_snapshot(), {"active_pilots": 42})
