import factory
from unittest.mock import patch, MagicMock

from django.db.models import signals

from app.test import TestCase

from eveonline.client import EsiResponse
from eveonline.models import EveAlliance, EveCorporation, EveCharacter

from structures.tasks import (
    process_structure_notifications,
    fetch_structure_notifications_for_character,
    update_corporation_structures,
)
from structures.models import (
    EveStructurePing,
    EveStructure,
)
from structures.tests.test_helpers import make_character


class StructureTaskTests(TestCase):
    """Task tests for structures and timers"""

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.utils.get_esi_downtime_countdown", return_value=0)
    @patch("structures.tasks.discord")
    @patch("structures.tasks.EsiClient")
    @patch(
        "structures.tasks.fetch_structure_notifications_for_character.apply_async"
    )
    def test_process_structure_notifications(
        self, apply_async_mock, esi_mock, discord_mock, get_downtime_mock
    ):
        def run_task_inline(args, countdown=0, **kwargs):
            if countdown == 0:
                fetch_structure_notifications_for_character(args[0])

        apply_async_mock.side_effect = run_task_inline

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

        corp = EveCorporation.objects.create(
            corporation_id=1001,
            name="MegaCorp",
            alliance=EveAlliance.objects.create(alliance_id=99011978),
        )
        # Corp must have a structure so it's included in notification polling
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
        # Character 2005: character_id % 10 == 5, so they're in the bucket for minute 5
        make_character(
            2005,
            corp,
            ["esi-characters.read_notifications.v1"],
        )

        total_scheduled, _ = process_structure_notifications(5)

        self.assertEqual(1, total_scheduled)
        apply_async_mock.assert_called_once_with(
            args=[2005],
            countdown=0,
        )

        self.assertEqual(1, EveStructurePing.objects.count())
        ping = EveStructurePing.objects.first()
        self.assertEqual(1049253339308, ping.structure_id)
        self.assertEqual("Pilot 2005", ping.reported_by.character_name)
        self.assertEqual("StructureLostArmor", ping.notification_type)
        self.assertEqual(16, ping.event_time.minute)

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    @patch("eveonline.utils.get_esi_downtime_countdown", return_value=0)
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
        esi.get_solar_system.return_value = MagicMock(name="Home")

        EveStructure.objects.create(
            id=100001,
            corporation=corp,
            system_id=100001,
            type_id=100001,
            reinforce_hour=23,
        )

        update_corporation_structures(corp.corporation_id)
