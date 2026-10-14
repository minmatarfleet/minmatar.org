from django.db.models import signals
from django.test import Client

from app.test import TestCase
from eveonline.helpers.corporations.slugs import (
    FL33T_ID,
    corporation_for_slug,
    corporation_slug,
)
from eveonline.models import EveAlliance, EveCorporation

BASE_URL = "/api/eveonline/corporations/"


class CorporationSlugTestCase(TestCase):
    def setUp(self):
        signals.post_save.disconnect(
            sender=EveAlliance,
            dispatch_uid="eve_alliance_post_save",
        )
        super().setUp()
        self.client = Client()

    def _corp(self, corporation_id, name, alliance=None):
        return EveCorporation.objects.create(
            corporation_id=corporation_id, name=name, alliance=alliance
        )

    def test_slug_strips_punctuation(self):
        self.assertEqual("rattini-tribe", corporation_slug("Rattini Tribe"))
        self.assertEqual(
            "every-little-helps", corporation_slug("Every Little Helps.")
        )
        self.assertEqual("shea-en-m-taal", corporation_slug("Shea'en M'Taal"))
        self.assertEqual("", corporation_slug("..."))

    def test_resolves_names_with_punctuation(self):
        corp = self._corp(1335603455, "Shea'en M'Taal")
        self.assertEqual(corp, corporation_for_slug("shea-en-m-taal"))
        self.assertIsNone(corporation_for_slug("shea-en"))
        self.assertIsNone(corporation_for_slug("Shea'en"))

    def test_alliance_corp_wins_a_shared_slug(self):
        self._corp(1001, "Every Little Helps")
        alliance = EveAlliance.objects.create(
            alliance_id=FL33T_ID, name="Minmatar Fleet Alliance"
        )
        member = self._corp(2002, "Every Little Helps.", alliance)
        self.assertEqual(member, corporation_for_slug("every-little-helps"))

    def test_endpoint_returns_id_and_canonical_slug(self):
        self._corp(98726134, "Rattini Tribe")
        response = self.client.get(
            BASE_URL + "corporations/by-slug/rattini-tribe"
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"corporation_id": 98726134, "slug": "rattini-tribe"},
            response.json(),
        )
        missing = self.client.get(BASE_URL + "corporations/by-slug/nobody")
        self.assertEqual(404, missing.status_code)
