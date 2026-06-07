"""Tests for character clone sync helpers."""

import factory
from unittest.mock import patch, MagicMock

from django.db.models import signals

from app.test import TestCase
from eveonline.client import EsiClient, EsiResponse
from eveonline.helpers.characters.clones import (
    match_active_implants_to_clone,
    update_character_clones,
)
from eveonline.models import EveCharacter, EveCharacterClone


CLONES_RESPONSE = {
    "home_location": {
        "location_id": 60003760,
        "location_type": "station",
    },
    "jump_clones": [
        {
            "jump_clone_id": 1,
            "name": "Home",
            "location_id": 60003760,
            "location_type": "station",
            "implants": [19540, 19551],
        },
        {
            "jump_clone_id": 2,
            "name": "Empty",
            "location_id": 60003761,
            "location_type": "station",
            "implants": [],
        },
    ],
}


class UpdateCharacterClonesTest(TestCase):
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.clones.build_clone_implant_list")
    @patch("eveonline.helpers.characters.clones.resolve_location_name")
    @patch("eveonline.helpers.characters.clones.EsiClient")
    def test_syncs_jump_clones_and_active_flag(
        self,
        esi_mock_cls,
        resolve_mock,
        build_implants_mock,
    ):
        char = EveCharacter.objects.create(
            character_id=7001,
            character_name="Clone Tester",
        )
        resolve_mock.return_value = "Amarr VIII"

        def fake_implants(type_ids):
            return [
                {
                    "type_id": tid,
                    "type_name": f"Implant {tid}",
                    "estimated_price_isk": 1_000_000,
                }
                for tid in type_ids
            ]

        build_implants_mock.side_effect = fake_implants

        esi = MagicMock(spec=EsiClient)
        esi_mock_cls.return_value = esi
        esi.get_character_clones.return_value = EsiResponse(
            response_code=0, data=CLONES_RESPONSE
        )
        esi.get_character_implants.return_value = EsiResponse(
            response_code=0, data=[19540, 19551]
        )

        count = update_character_clones(7001)

        self.assertEqual(count, 2)
        char.refresh_from_db()
        self.assertEqual(char.medical_clone_location_id, 60003760)
        self.assertEqual(char.medical_clone_location_name, "Amarr VIII")
        self.assertIsNotNone(char.clones_synced_at)

        clones = EveCharacterClone.objects.filter(character=char).order_by(
            "clone_id"
        )
        self.assertEqual(clones.count(), 2)
        self.assertTrue(clones.get(clone_id=1).is_active)
        self.assertFalse(clones.get(clone_id=2).is_active)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.clones.EsiClient")
    def test_skips_suspended_character(self, esi_mock_cls):
        EveCharacter.objects.create(
            character_id=7002,
            character_name="Suspended",
            esi_suspended=True,
        )
        count = update_character_clones(7002)
        self.assertEqual(count, 0)
        esi_mock_cls.assert_not_called()


class MatchActiveImplantsTest(TestCase):
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_marks_matching_clone_active(self):
        char = EveCharacter.objects.create(
            character_id=7003,
            character_name="Matcher",
        )
        EveCharacterClone.objects.create(
            character=char,
            clone_id=10,
            implants=[
                {"type_id": 1, "type_name": "A", "estimated_price_isk": 1},
                {"type_id": 2, "type_name": "B", "estimated_price_isk": 2},
            ],
        )
        EveCharacterClone.objects.create(
            character=char,
            clone_id=11,
            implants=[],
        )

        match_active_implants_to_clone(char, [1, 2])

        self.assertTrue(EveCharacterClone.objects.get(clone_id=10).is_active)
        self.assertFalse(EveCharacterClone.objects.get(clone_id=11).is_active)
