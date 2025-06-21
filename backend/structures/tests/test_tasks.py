import factory
from unittest.mock import patch, MagicMock

from django.db.models import signals

from app.test import TestCase

from eveonline.client import EsiResponse
from eveonline.models import EveAlliance, EveCorporation, EveCharacter

from structures.tasks import (
    setup_structure_managers,
    structure_managers_for_minute,
    process_structure_notifications,
    update_corporation_structures,
)
from structures.models import (
    EveStructureManager,
    EveStructurePing,
    EveStructure,
)
from structures.tests.test_helpers import make_character


class StructureTaskTests(TestCase):
    """Task tests for structures and timers"""

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_setup_structure_managers(self):
        self.assertEqual(0, EveStructureManager.objects.count())

        corp = EveCorporation.objects.create(
            corporation_id=1001,
            name="MegaCorp",
        )
        chars = [
            EveCharacter.objects.create(
                character_id=2001,
                character_name="Director 1",
            ),
            EveCharacter.objects.create(
                character_id=2002,
                character_name="Director 2",
            ),
            EveCharacter.objects.create(
                character_id=2003,
                character_name="CEO",
            ),
        ]

        setup_structure_managers(corp, chars)

        managers = EveStructureManager.objects.all().order_by("poll_time")
        self.assertEqual(3, managers.count())
        self.assertEqual(0, managers[0].poll_time)
        self.assertEqual(3, managers[1].poll_time)
        self.assertEqual(6, managers[2].poll_time)

        minute_3 = structure_managers_for_minute(3)
        self.assertEqual(1, minute_3.count())

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("structures.tasks.discord")
    @patch("structures.tasks.EsiClient")
    def test_process_structure_notifications(self, esi_mock, discord_mock):
        esi = esi_mock.return_value
        esi.get_character_notifications.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "notification_id": 1234567890,
                    "timestamp": "2025-05-24 03:16:00+00:00",
                    "type": "StructureLostArmor",
                    "text": """
                        structureID: &id001 1049253339308
                        """,
                }
            ],
        )

        scopes = [
            "esi-characters.read_notifications.v1",
            "esi-fleets.read_fleet.v1",
        ]
        corp = EveCorporation.objects.create(
            corporation_id=1001,
            name="MegaCorp",
            alliance=EveAlliance.objects.create(alliance_id=99011978),
        )

        EveStructureManager.objects.create(
            corporation=corp,
            character=make_character(2001, corp, scopes),
            poll_time=0,
        )
        EveStructureManager.objects.create(
            corporation=corp,
            character=make_character(2002, corp, scopes),
            poll_time=5,
        )

        total_found, total_new = process_structure_notifications(5)

        self.assertEqual(1, total_found)
        self.assertEqual(0, total_new)

        self.assertIsNotNone(
            EveStructureManager.objects.get(
                character__character_id=2002
            ).last_polled
        )

        self.assertEqual(1, EveStructurePing.objects.count())
        ping = EveStructurePing.objects.first()
        self.assertEqual(1049253339308, ping.structure_id)
        self.assertEqual("Pilot 2002", ping.reported_by.character_name)
        self.assertEqual("StructureLostArmor", ping.notification_type)
        self.assertEqual(16, ping.event_time.minute)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("structures.tasks.esi_for")
    def test_update_corporation_structures(self, esi_mock):
        corp = EveCorporation.objects.create(
            corporation_id=2001,
            name="MegaCorp",
            ceo=EveCharacter.objects.create(
                character_id=1001,
                character_name="Mr CEO",
                esi_token_level="ceo",
            ),
        )

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
        esi.get_solar_system.return_value = MagicMock(name="Home")

        EveStructure.objects.create(
            id=100001,
            corporation=corp,
            system_id=100001,
            type_id=100001,
            reinforce_hour=23,
        )

        update_corporation_structures(corp.corporation_id)
