"""Tests for the corporation alliance override (BUILD -> FL33T)."""

from unittest.mock import patch

import factory
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import signals

from app.test import TestCase
from eveonline.client import EsiResponse
from eveonline.constants import (
    MINMATAR_FLEET_ALLIANCE_ID,
    MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID,
)
from eveonline.helpers.alliances import alliance_corporations
from eveonline.helpers.characters import update_character_with_affiliations
from eveonline.helpers.corporations.alliance_override import (
    apply_alliance_override,
)
from eveonline.models import EveAlliance, EveCharacter, EveCorporation

CORP_ID = 98705678
OTHER_CORP_ID = 98838663
ELSEWHERE_ALLIANCE_ID = 99003581


class AllianceOverrideTestCase(TestCase):
    def setUp(self):
        super().setUp()
        # No ESI fetches from EveAlliance / EveCharacter save signals.
        muted = factory.django.mute_signals(
            signals.pre_save, signals.post_save
        )
        muted.__enter__()  # pylint: disable=unnecessary-dunder-call
        self.addCleanup(muted.__exit__, None, None, None)
        self.fl33t = EveAlliance.objects.create(
            alliance_id=MINMATAR_FLEET_ALLIANCE_ID, ticker="FL33T"
        )
        self.build = EveAlliance.objects.create(
            alliance_id=MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID, ticker="BUILD"
        )
        self.corporation = EveCorporation.objects.create(
            corporation_id=CORP_ID,
            alliance=self.build,
            alliance_override_from=self.build,
            alliance_override_to=self.fl33t,
        )

    def _sync_character(self, corporation_id, alliance_id):
        character, _ = EveCharacter.objects.get_or_create(
            character_id=96129158, defaults={"corporation_id": corporation_id}
        )
        update_character_with_affiliations(
            character.character_id, corporation_id, alliance_id=alliance_id
        )
        character.refresh_from_db()
        return character

    def _populate(self, esi_corporation_alliance_id):
        with patch("eveonline.models.corporations.EsiClient") as esi:
            esi.return_value.get_corporation.return_value = EsiResponse(
                response_code=200,
                data={
                    "name": "Build Corp",
                    "ticker": "BLDC",
                    "member_count": 10,
                    "alliance_id": esi_corporation_alliance_id,
                    "ceo_id": 96129158,
                },
            )
            self.corporation.populate()
        self.corporation.refresh_from_db()

    def test_affiliation_sync_maps_from_to(self):
        character = self._sync_character(
            CORP_ID, MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID
        )
        self.assertEqual(character.alliance_id, MINMATAR_FLEET_ALLIANCE_ID)

    def test_affiliation_sync_drops_override_after_leaving_alliance(self):
        self._sync_character(CORP_ID, MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID)
        character = self._sync_character(CORP_ID, ELSEWHERE_ALLIANCE_ID)
        self.assertEqual(character.alliance_id, ELSEWHERE_ALLIANCE_ID)

    def test_affiliation_sync_ignores_other_corporations(self):
        character = self._sync_character(
            OTHER_CORP_ID, MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID
        )
        self.assertEqual(
            character.alliance_id, MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID
        )

    def test_populate_keeps_override_while_in_from_alliance(self):
        self._populate(MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID)
        self.assertEqual(self.corporation.alliance, self.fl33t)
        self.assertEqual(self.corporation.alliance_override_to, self.fl33t)
        self.assertEqual(self.corporation.type, "alliance")
        self.assertIn(self.corporation, alliance_corporations())

    def test_populate_removes_override_after_leaving_alliance(self):
        self._populate(None)
        self.assertIsNone(self.corporation.alliance)
        self.assertIsNone(self.corporation.alliance_override_from)
        self.assertIsNone(self.corporation.alliance_override_to)
        self.assertNotIn(self.corporation, alliance_corporations())

    @patch("groups.tasks.update_affiliation.delay")
    def test_apply_moves_members_now(self, update_affiliation_delay):
        user = User.objects.create(username="override-pilot")
        member = EveCharacter.objects.create(
            character_id=96129158,
            corporation_id=CORP_ID,
            alliance_id=MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID,
            user=user,
        )
        outsider = EveCharacter.objects.create(
            character_id=149027055,
            corporation_id=OTHER_CORP_ID,
            alliance_id=MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID,
        )

        changed = apply_alliance_override(self.corporation)

        self.assertEqual(changed, 1)
        member.refresh_from_db()
        outsider.refresh_from_db()
        self.corporation.refresh_from_db()
        self.assertEqual(member.alliance_id, MINMATAR_FLEET_ALLIANCE_ID)
        self.assertEqual(
            outsider.alliance_id, MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID
        )
        self.assertEqual(self.corporation.alliance, self.fl33t)
        update_affiliation_delay.assert_called_once_with(user.id)

    @patch("eveonline.tasks.update_corporation.delay")
    def test_removing_override_refreshes_from_esi(self, update_delay):
        self.corporation.alliance_override_from = None
        self.corporation.alliance_override_to = None
        self.corporation.save()
        self.assertEqual(apply_alliance_override(self.corporation), 0)
        update_delay.assert_called_once_with(CORP_ID)

    @patch("eveonline.tasks.update_corporation.delay")
    def test_apply_skips_corporation_not_in_from_alliance(self, update_delay):
        self.corporation.alliance = None
        self.corporation.save()
        self.assertEqual(apply_alliance_override(self.corporation), 0)
        self.corporation.refresh_from_db()
        self.assertIsNone(self.corporation.alliance)
        update_delay.assert_called_once_with(CORP_ID)

    def test_clean_requires_both_alliances(self):
        self.corporation.alliance_override_to = None
        with self.assertRaises(ValidationError):
            self.corporation.clean()
        self.corporation.alliance_override_to = self.build
        with self.assertRaises(ValidationError):
            self.corporation.clean()
