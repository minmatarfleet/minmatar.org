from django.test import TestCase
from django.utils import timezone

from eveonline.models import EveCorporation
from exits.models import Departure


class ModelDefaultsTest(TestCase):
    def setUp(self):
        self.corporation = EveCorporation.objects.create(
            corporation_id=98000001, name="Example Corp"
        )

    def test_track_exits_defaults_off(self):
        self.assertIs(self.corporation.track_exits, False)

    def test_departure_defaults(self):
        departure = Departure.objects.create(
            corporation=self.corporation,
            character_id=2112000001,
            first_missing_at=timezone.now(),
        )
        self.assertEqual(departure.status, "pending")
        self.assertEqual(departure.reason, "")
        self.assertIsNone(departure.can_rejoin)
