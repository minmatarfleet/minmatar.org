import factory
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.db import IntegrityError, transaction
from django.db.models import signals
from django.db.models.query import QuerySet
from django.utils import timezone

from app.test import TestCase

from eveonline.client import EsiResponse
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterNotification,
    EveCorporation,
)

from structures.tasks import (
    process_structure_notifications,
    store_structure_ping,
    update_corporation_structures,
    update_structures,
)
from structures.models import (
    EveStructurePing,
    EveStructure,
)
from structures.tests.test_helpers import make_character


class StructureTaskTests(TestCase):
    """Task tests for structures and timers"""

    def _structure_corp(self, corporation_id=1001):
        corp = EveCorporation.objects.create(
            corporation_id=corporation_id,
            name=f"Corp {corporation_id}",
            alliance=EveAlliance.objects.get_or_create(alliance_id=99011978)[
                0
            ],
        )
        EveStructure.objects.create(
            id=1049253339308,
            corporation=corp,
            system_id=30002538,
            system_name="Test System",
            type_id=35826,
            type_name="Astrahus",
            name="Test Structure",
            reinforce_hour=12,
        )
        return corp

    def _stored(self, character, notification_id, kind="StructureLostArmor"):
        return EveCharacterNotification.objects.create(
            character=character,
            notification_id=notification_id,
            type=kind,
            timestamp=timezone.now() - timedelta(minutes=4),
            text="structureID: &id001 1049253339308\n",
        )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("structures.tasks.discord")
    def test_process_structure_notifications(self, discord_mock):
        corp = self._structure_corp()
        character = make_character(2005, corp, [])
        self._stored(character, 1234567890)
        self._stored(character, 1234567891, kind="CorpAppNewMsg")

        found, new = process_structure_notifications()

        self.assertEqual((1, 1), (found, new))
        discord_mock.create_message.assert_called_once()
        ping = EveStructurePing.objects.get()
        self.assertEqual(1049253339308, ping.structure_id)
        self.assertEqual("Pilot 2005", ping.reported_by.character_name)
        self.assertEqual("StructureLostArmor", ping.notification_type)

        # A second run finds nothing left to do.
        self.assertEqual((0, 0), process_structure_notifications())
        discord_mock.create_message.assert_called_once()

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("structures.tasks.discord")
    def test_same_notification_is_stored_once(self, discord_mock):
        corp = self._structure_corp()
        character = make_character(2007, corp, [])
        row = self._stored(character, 1234567893)

        self.assertTrue(store_structure_ping(row))
        self.assertFalse(store_structure_ping(row))
        self.assertEqual(1, EveStructurePing.objects.count())
        discord_mock.create_message.assert_called_once()

        with self.assertRaises(IntegrityError), transaction.atomic():
            EveStructurePing.objects.create(
                notification_id=1234567893,
                notification_type="StructureLostArmor",
                summary="",
            )

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("structures.tasks.discord")
    def test_losing_a_race_does_not_raise_or_post(self, discord_mock):
        """Another worker inserts between our lookup and our insert (M4)."""
        corp = self._structure_corp()
        character = make_character(2008, corp, [])
        row = self._stored(character, 1234567894)
        EveStructurePing.objects.create(
            notification_id=1234567894,
            notification_type="StructureLostArmor",
            summary="",
        )
        real_get = QuerySet.get
        calls = []

        def get_missing_first(qs, *args, **kwargs):
            calls.append(kwargs)
            if qs.model is EveStructurePing and len(calls) == 1:
                raise EveStructurePing.DoesNotExist
            return real_get(qs, *args, **kwargs)

        with patch.object(QuerySet, "get", get_missing_first):
            self.assertFalse(store_structure_ping(row))

        self.assertEqual(2, len(calls))
        self.assertEqual(1, EveStructurePing.objects.count())
        discord_mock.create_message.assert_not_called()

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("structures.tasks.discord")
    def test_characters_outside_structure_corps_are_ignored(
        self, discord_mock
    ):
        self._structure_corp()
        elsewhere = EveCorporation.objects.create(
            corporation_id=2002, name="Someone Else"
        )
        character = make_character(2006, elsewhere, [])
        self._stored(character, 1234567892)

        self.assertEqual((0, 0), process_structure_notifications())
        self.assertFalse(EveStructurePing.objects.exists())
        discord_mock.create_message.assert_not_called()

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("structures.tasks.get_esi_downtime_countdown", return_value=0)
    @patch("structures.tasks.esi_for")
    @patch("structures.tasks.get_director_with_scope")
    def test_update_corporation_structures(
        self, get_director_mock, esi_mock, get_downtime_mock
    ):
        ceo = EveCharacter.objects.create(
            character_id=1001,
            character_name="Mr CEO",
            esi_token_level="ceo",
        )
        corp = EveCorporation.objects.create(
            corporation_id=2001,
            name="MegaCorp",
            ceo=ceo,
        )
        get_director_mock.return_value = ceo

        esi = esi_mock.return_value
        esi.get_corp_structures.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "structure_id": 100001,
                    "corporation_id": corp.corporation_id,
                    "name": "MegaStructure",
                    "system_id": 100001,
                    "type_id": 100001,
                    "reinforce_hour": 12,
                    "state": "testing",
                    "state_timer_start": None,
                    "state_timer_end": None,
                    "fuel_expires": None,
                }
            ],
        )
        system_mock = MagicMock()
        system_mock.name = "Home"
        esi.get_solar_system.return_value = system_mock
        type_mock = MagicMock()
        type_mock.name = "Astrahus"
        esi.get_eve_type.return_value = type_mock

        EveStructure.objects.create(
            id=100001,
            corporation=corp,
            system_id=100001,
            type_id=100001,
            reinforce_hour=23,
        )

        update_corporation_structures(corp.corporation_id)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("structures.tasks.get_esi_downtime_countdown", return_value=0)
    @patch("structures.tasks.esi_for")
    @patch("structures.tasks.get_director_with_scope")
    def test_update_corporation_structures_restores_soft_deleted(
        self, get_director_mock, esi_mock, get_downtime_mock
    ):
        """A soft-deleted structure reappearing in ESI is restored, not
        re-created (which would previously raise an IntegrityError)."""
        ceo = EveCharacter.objects.create(
            character_id=1002,
            character_name="Mr CEO 2",
            esi_token_level="ceo",
        )
        corp = EveCorporation.objects.create(
            corporation_id=2002,
            name="MegaCorp2",
            ceo=ceo,
        )
        get_director_mock.return_value = ceo

        structure = EveStructure.objects.create(
            id=100002,
            corporation=corp,
            system_id=100002,
            system_name="Old System",
            type_id=100002,
            type_name="Old Type",
            name="Old Name",
            reinforce_hour=10,
        )
        structure.delete()
        self.assertIsNotNone(EveStructure.all_objects.get(id=100002).deleted)

        esi = esi_mock.return_value
        esi.get_corp_structures.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "structure_id": 100002,
                    "corporation_id": corp.corporation_id,
                    "name": "MegaStructure",
                    "system_id": 100002,
                    "type_id": 100002,
                    "reinforce_hour": 12,
                    "state": "shield_vulnerable",
                    "state_timer_start": None,
                    "state_timer_end": None,
                    "fuel_expires": None,
                }
            ],
        )
        system_mock = MagicMock()
        system_mock.name = "Home System"
        esi.get_solar_system.return_value = system_mock
        type_mock = MagicMock()
        type_mock.name = "Astrahus"
        esi.get_eve_type.return_value = type_mock

        update_corporation_structures(corp.corporation_id)

        restored = EveStructure.objects.get(id=100002)
        self.assertIsNone(restored.deleted)
        self.assertEqual("MegaStructure", restored.name)
        self.assertEqual("shield_vulnerable", restored.state)
        self.assertEqual("Home System", restored.system_name)
        self.assertEqual("Astrahus", restored.type_name)


class StructureFanOutTests(TestCase):
    """The fan-outs queue only work that will run."""

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("structures.tasks.update_corporation_structures.delay")
    @patch("structures.tasks.get_director_with_scope")
    def test_update_structures_skips_corps_without_a_director(
        self, get_director_mock, delay_mock
    ):
        alliance = EveAlliance.objects.create(alliance_id=99011978)
        with_director = EveCorporation.objects.create(
            corporation_id=3001, name="Has Director", alliance=alliance
        )
        EveCorporation.objects.create(
            corporation_id=3002, name="No Director", alliance=alliance
        )
        director = EveCharacter.objects.create(
            character_id=4001, character_name="Director"
        )
        get_director_mock.side_effect = lambda corp, scopes: (
            director if corp.pk == with_director.pk else None
        )

        self.assertEqual(1, update_structures())

        delay_mock.assert_called_once_with(3001)

    @patch("structures.tasks.get_esi_downtime_countdown", return_value=300)
    @patch("structures.tasks.update_corporation_structures.apply_async")
    def test_downtime_skips_instead_of_queueing_a_retry(
        self, structures_mock, downtime_mock
    ):
        self.assertIsNone(update_corporation_structures(2001))
        structures_mock.assert_not_called()
