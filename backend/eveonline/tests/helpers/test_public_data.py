import factory
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.db.models import signals
from esi.exceptions import ESIErrorLimitException, HTTPClientError
from esi.models import Token

from app.test import TestCase

from eveonline.client import EsiResponse
from eveonline.helpers.characters.public_data import (
    apply_character_public_data,
    update_character_public_data,
)
from eveonline.models import EveCharacter
from eveonline.signals import populate_eve_character_public_data
from eveonline.tasks.characters import update_all_character_public_data


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

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.public_data.esi_public")
    def test_update_character_public_data_marks_deleted_on_404(
        self, esi_public
    ):
        user = User.objects.create(username="pilot")
        token = Token.objects.create(user=user, character_id=10005)
        EveCharacter.objects.create(
            character_id=10005,
            character_name="Gone Pilot",
            user=user,
            token=token,
            corporation_id=2001,
        )
        esi_public.return_value.get_character_public_data.return_value = (
            EsiResponse(
                response_code=404,
                response=HTTPClientError(
                    404, {}, {"error": "Character has been deleted!"}
                ),
            )
        )

        updated = update_character_public_data(10005)

        self.assertFalse(updated)
        character = EveCharacter.objects.get(character_id=10005)
        self.assertTrue(character.esi_deleted)
        self.assertIsNotNone(character.esi_deleted_at)
        self.assertIsNone(character.user_id)
        self.assertIsNone(character.token_id)
        self.assertEqual(0, Token.objects.filter(character_id=10005).count())
        self.assertEqual("Gone Pilot", character.character_name)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.public_data.esi_public")
    def test_update_character_public_data_skips_already_deleted(
        self, esi_public
    ):
        EveCharacter.objects.create(
            character_id=10006,
            character_name="Already Gone",
            esi_deleted=True,
        )

        updated = update_character_public_data(10006)

        self.assertFalse(updated)
        esi_public.return_value.get_character_public_data.assert_not_called()

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.helpers.characters.public_data.esi_public")
    def test_update_character_public_data_raises_on_error_limit(
        self, esi_public
    ):
        EveCharacter.objects.create(character_id=10007, character_name="Alive")
        esi_public.return_value.get_character_public_data.return_value = (
            EsiResponse(
                response_code=420,
                response=ESIErrorLimitException(reset=12),
            )
        )

        with self.assertRaises(ESIErrorLimitException):
            update_character_public_data(10007)

        character = EveCharacter.objects.get(character_id=10007)
        self.assertFalse(character.esi_deleted)


class UpdateAllCharacterPublicDataTests(TestCase):
    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch(
        "eveonline.tasks.characters.refresh_character_public_data",
        autospec=True,
    )
    def test_excludes_esi_deleted_characters(self, refresh_mock):
        refresh_mock.return_value = True
        EveCharacter.objects.create(character_id=20001, character_name="Live")
        EveCharacter.objects.create(
            character_id=20002,
            character_name="Dead",
            esi_deleted=True,
        )

        updated = update_all_character_public_data()

        self.assertEqual(1, updated)
        refresh_mock.assert_called_once_with(20001)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch(
        "eveonline.tasks.characters.refresh_character_public_data",
        autospec=True,
    )
    def test_aborts_on_esi_error_limit(self, refresh_mock):
        EveCharacter.objects.create(character_id=20003, character_name="A")
        EveCharacter.objects.create(character_id=20004, character_name="B")
        EveCharacter.objects.create(character_id=20005, character_name="C")

        def side_effect(character_id):
            if character_id == 20004:
                raise ESIErrorLimitException(reset=5)
            return True

        refresh_mock.side_effect = side_effect

        updated = update_all_character_public_data()

        self.assertEqual(1, updated)
        called_ids = [c.args[0] for c in refresh_mock.call_args_list]
        self.assertEqual([20003, 20004], called_ids)
