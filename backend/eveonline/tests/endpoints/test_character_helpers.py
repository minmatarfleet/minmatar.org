"""Tests for character endpoint helpers."""

from django.db.models import signals
from esi.models import Token

from app.test import TestCase
from applications.models import EveCorporationApplication
from eveonline.constants import (
    MINMATAR_FLEET_ALLIANCE_ID,
    MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID,
)
from eveonline.endpoints.characters._helpers import build_character_response
from eveonline.helpers.characters import set_primary_character
from eveonline.models import EveCharacter


class BuildCharacterResponseTestCase(TestCase):
    """MAIN_NOT_IN_FL33T and related flags on character summaries."""

    def setUp(self):
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCorporationApplication,
            dispatch_uid="eve_corporation_application_post_save",
        )
        super().setUp()

    def _character(self, alliance_id, character_id=10001):
        token = Token.objects.create(
            user=self.user,
            character_id=character_id,
        )
        char = EveCharacter.objects.create(
            character_id=character_id,
            character_name="Test Pilot",
            user=self.user,
            token=token,
            alliance_id=alliance_id,
            esi_token_level="Industry",
        )
        char.tag_count = 1
        set_primary_character(self.user, char)
        return char

    def test_alliance_main_is_not_flagged(self):
        char = self._character(MINMATAR_FLEET_ALLIANCE_ID)
        item = build_character_response(char, char)
        self.assertNotIn("MAIN_NOT_IN_FL33T", item.flags)

    def test_associates_main_is_not_flagged(self):
        """Associates alliance ticker is BUILD; same id as BUILD corps."""
        char = self._character(MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID)
        item = build_character_response(char, char)
        self.assertNotIn("MAIN_NOT_IN_FL33T", item.flags)

    def test_unaffiliated_main_is_flagged(self):
        char = self._character(None)
        item = build_character_response(char, char)
        self.assertIn("MAIN_NOT_IN_FL33T", item.flags)

    def test_pending_application_suppresses_flag(self):
        char = self._character(None)
        EveCorporationApplication.objects.create(
            user=self.user,
            corporation_id=123,
            status="pending",
        )
        item = build_character_response(char, char)
        self.assertNotIn("MAIN_NOT_IN_FL33T", item.flags)
