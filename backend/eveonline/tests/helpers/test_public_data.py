import factory
from unittest.mock import MagicMock, patch

from django.db.models import signals

from app.test import TestCase

from eveonline.client import EsiResponse
from eveonline.helpers.characters.public_data import (
    apply_character_public_data,
    update_character_public_data,
)
from eveonline.models import EveCharacter
from eveonline.signals import populate_eve_character_public_data


class CharacterPublicDataHelperTests(TestCase):
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_apply_character_public_data_updates_security_status(self):
        character = EveCharacter.objects.create(
            character_id=10001,
            character_name="Old Name",
            corporation_id=100,
            security_status=0.0,
        )

        updated = apply_character_public_data(
            character,
            {
                "name": "New Name",
                "corporation_id": 200,
                "security_status": -2.5,
            },
        )

        self.assertTrue(updated)
        self.assertEqual("New Name", character.character_name)
        self.assertEqual(200, character.corporation_id)
        self.assertEqual(-2.5, character.security_status)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_apply_character_public_data_no_change(self):
        character = EveCharacter.objects.create(
            character_id=10002,
            character_name="Pilot",
            corporation_id=200,
            security_status=5.0,
        )

        updated = apply_character_public_data(
            character,
            {
                "name": "Pilot",
                "corporation_id": 200,
                "security_status": 5.0,
            },
        )

        self.assertFalse(updated)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.public_data.esi_public")
    def test_update_character_public_data(self, esi_public):
        esi_public.return_value.get_character_public_data.return_value = (
            EsiResponse(
                response_code=200,
                data={
                    "name": "Bob",
                    "corporation_id": 2001,
                    "security_status": 1.2,
                },
            )
        )

        EveCharacter.objects.create(character_id=10003)

        updated = update_character_public_data(10003)

        self.assertTrue(updated)
        character = EveCharacter.objects.get(character_id=10003)
        self.assertEqual("Bob", character.character_name)
        self.assertEqual(2001, character.corporation_id)
        self.assertEqual(1.2, character.security_status)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.signals.update_character_public_data")
    def test_populate_eve_character_public_data_signal(self, update_mock):
        update_mock.return_value = True

        instance = EveCharacter.objects.create(character_id=10004)
        populate_eve_character_public_data(MagicMock(), instance, True)

        update_mock.assert_called_once_with(10004)
