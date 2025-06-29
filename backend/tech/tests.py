import logging
import factory

from unittest.mock import patch, MagicMock

from django.db.models import signals
from django.test import Client, SimpleTestCase

from esi.models import Token
from app.test import TestCase
from eveonline.client import EsiResponse
from eveonline.models import (
    EvePlayer,
    EveCharacter,
    EveTag,
    EveCharacterTag,
    EveCorporation,
)
from eveonline.helpers.characters import set_primary_character
from fleets.models import EveFleet, EveFleetAudience
from tech.docker import (
    parse_docker_logs,
    sort_chronologically,
    DockerLogEntry,
    DockerLogQuery,
)
from tech.dbviews import create_all_views, select_all

BASE_URL = "/api/tech"
logger = logging.getLogger(__name__)


class DockerLogsTestCase(SimpleTestCase):
    """Non-django unit test for the docker logs code."""

    def test_log_entries(self):
        log_text_a = """
        2025-05-03T10:01:01.000000000Z 2025-05-03 10:01:01,000 WARNING  [log.test] Log entry 1
        2025-05-03T10:01:03.000000000Z 2025-05-03 10:01:03,000 WARNING  [log.test] Log entry 3
        """
        logs = parse_docker_logs("container_a", log_text_a)

        log_text_b = """
        2025-05-03T10:01:02.000000000Z 2025-05-03 10:01:01,000 WARNING  [log.test] Log entry 2
        """
        logs += parse_docker_logs("container_b", log_text_b)

        sort_chronologically(logs)

        self.assertIn("Log entry 1", str(logs[0]))
        self.assertIn("container_a", str(logs[0]))
        self.assertIn("Log entry 2", str(logs[1]))
        self.assertIn("container_b", str(logs[1]))
        self.assertIn("Log entry 3", str(logs[2]))
        self.assertIn("container_a", str(logs[2]))

    def test_search_log_entries(self):
        log_text = """
        2025-05-03T10:01:01.000000000Z 2025-05-03 10:01:01,000 WARNING  [log.test] Something red
        2025-05-03T10:01:02.000000000Z 2025-05-03 10:01:02,000 WARNING  [log.test] Something blue
        2025-05-03T10:01:03.000000000Z 2025-05-03 10:01:03,000 WARNING  [log.test] Blue Monday
        2025-05-03T10:01:04.000000000Z 2025-05-03 10:01:04,000 WARNING  [log.test] Green Friday
        """

        query = DockerLogQuery(
            containers="a",
            start_time="2025-05-03T10:01:01.000000000Z",
            end_time="2025-05-03T10:59:59.000000000Z",
            search_for="blue",
        )
        logs = parse_docker_logs("container_a", log_text, query)

        self.assertEqual(2, len(logs))
        for entry in logs:
            self.assertIn("blue", str(entry).lower())


class DatabaseViewsTestCase(TestCase):
    """Unit tests for the database view creation"""

    @factory.django.mute_signals(signals.pre_save, signals.post_save)
    def test_create_views(self):
        create_all_views()

        primary = EveCharacter.objects.create(
            character_id=1001,
            character_name="Pilot 1",
            user=self.user,
        )
        EveCharacter.objects.create(
            character_id=1002,
            character_name="Pilot 2",
            user=self.user,
        )
        EvePlayer.objects.create(
            user=self.user,
            primary_character=primary,
            nickname="Player 1",
        )

        data = select_all("primary_character")

        logger.info("View query results: %s", data)

        self.assertEqual(
            data,
            [
                (
                    self.user.id,
                    self.user.username,
                    1,
                    "Player 1",
                    1001,
                    "Pilot 1",
                    None,
                    None,
                ),
            ],
        )


class TechRoutesTestCase(TestCase):
    """Test cases for the tech router."""

    def setUp(self):
        # disconnect signals
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_public_data",
        )
        signals.post_save.disconnect(
            sender=EveCharacter,
            dispatch_uid="populate_eve_character_private_data",
        )

        # create test client
        self.client = Client()

        super().setUp()

    def test_ping(self):
        response = self.client.get(
            f"{BASE_URL}/ping",
        )
        self.assertEqual(response.status_code, 200)

    def test_fleet_tracking_poc(self):
        # esi_mock = esi_client_mock.return_value
        self.make_superuser()

        token = Token.objects.create(
            user=self.user,
            character_id=123456,
        )
        char = EveCharacter.objects.create(
            character_id=token.character_id,
            character_name="Test Char",
            token=token,
        )
        set_primary_character(self.user, char)

        EveFleetAudience.objects.create(
            name="Hidden",
            hidden=True,
            add_to_schedule=False,
        )

        response = self.client.get(
            f"{BASE_URL}/fleet_tracking_poc?start=False",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)

    def test_make_test_fleet(self):
        self.make_superuser()

        token = Token.objects.create(
            user=self.user,
            character_id=123456,
        )
        char = EveCharacter.objects.create(
            character_id=token.character_id,
            character_name="Test Char",
            token=token,
        )
        set_primary_character(self.user, char)

        EveFleetAudience.objects.create(
            name="Hidden",
            hidden=True,
            add_to_schedule=False,
        )

        response = self.client.post(
            f"{BASE_URL}/make_test_fleet",
            data={"description": "Test fleet 123", "type": "strategic"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        fleet_id = response.json()
        new_fleet = EveFleet.objects.filter(id=fleet_id).first()
        self.assertIsNotNone(new_fleet)
        self.assertEqual("Test fleet 123", new_fleet.description)

    def test_get_container_names(self):
        self.make_superuser()

        with patch("tech.router.container_names") as container_list_mock:
            container_list_mock.return_value = [
                "app",
                "frontend",
                "celery_1",
            ]
            response = self.client.get(
                f"{BASE_URL}/containers",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), ["app", "frontend", "celery_1"])

    @patch("tech.router.DockerContainer")
    @patch("tech.router.get_containers")
    def test_get_logs(self, container_list_mock, container_mock):
        self.make_superuser()

        container_mock.return_value.log_entries.return_value = [
            DockerLogEntry("app_container", "123", "Test logs"),
            DockerLogEntry("app_container", "124", "Line 2"),
        ]
        container = MagicMock()
        container.name = "app_container"

        container_list_mock.return_value = [container]

        response = self.client.get(
            f"{BASE_URL}/containers/app_container/logs",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("app_container", content)
        self.assertIn("Test logs", content)
        self.assertIn("Line 2", content)

    def test_setup_db_views(self):
        self.make_superuser()

        response = self.client.get(
            f"{BASE_URL}/dbviews",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)

    @patch("tech.router.esi_for")
    def test_get_notifications(self, esi_mock):
        self.make_superuser()

        esi = esi_mock.return_value
        esi.get_character_notifications.return_value = EsiResponse(
            response_code=200,
            data=[
                {
                    "notification_id": 2173324216,
                    "sender_id": 1000132,
                    "sender_type": "corporation",
                    "text": "Things going boom!",
                    "timestamp": "2025-05-23T20:26:00Z",
                    "type": "StructureUnderAttack",
                },
            ],
        )

        character = EveCharacter.objects.create(
            character_id=1001,
            character_name="Test pilot",
            user=self.user,
        )

        response = self.client.get(
            f"{BASE_URL}/notifications/{character.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual("StructureUnderAttack", data[0]["type"])

    def test_character_flags(self):
        self.make_superuser()

        char = EveCharacter.objects.create(
            character_id=1001,
            character_name="Test Pilot",
            user=self.user,
            esi_suspended=True,
            corporation=EveCorporation.objects.create(
                corporation_id=2001,
                name="MegaCorp",
            ),
        )

        response = self.client.get(
            f"{BASE_URL}/character_flags",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual("Test Pilot", data[0]["character_name"])
        self.assertEqual(0, data[0]["tag_count"])
        self.assertEqual("MegaCorp", data[0]["corp_name"])
        self.assertEqual(
            data[0]["flags"], ["ESI_SUSPENDED", "NO_TAGS", "NO_TOKENS"]
        )

        EveCharacterTag.objects.create(
            character=char,
            tag=EveTag.objects.create(
                title="DPS",
                description="F1 Pusher",
            ),
        )

        response = self.client.get(
            f"{BASE_URL}/character_flags",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(1, len(data))
        self.assertEqual(1, data[0]["tag_count"])
        self.assertEqual(data[0]["flags"], ["ESI_SUSPENDED", "NO_TOKENS"])

    def test_full_refresh(self):
        self.make_superuser()

        response = self.client.get(
            f"{BASE_URL}/force_refresh?username={self.user.username}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200)
        logger.info("Response content: %s", response.content)
