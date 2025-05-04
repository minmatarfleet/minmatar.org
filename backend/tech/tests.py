from unittest.mock import patch, Mock

from django.db.models import signals
from django.test import Client, SimpleTestCase
from django.contrib.auth.models import User

from esi.models import Token
from app.test import TestCase
from eveonline.models import EveCharacter, EvePrimaryCharacter
from tech.docker import (
    parse_docker_logs,
    sort_chronologically,
    DockerLogEntry,
    DockerLogQuery,
)

BASE_URL = "/api/tech"


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

    def test_get_character(self):
        self.make_superuser()

        user = User.objects.first()
        token = Token.objects.create(
            user=user,
            character_id=123456,
        )
        char = EveCharacter.objects.create(
            character_id=token.character_id,
            character_name="Test Char",
            token=token,
        )
        EvePrimaryCharacter.objects.create(
            character=char,
            user=user,
        )

        response = self.client.get(
            f"{BASE_URL}/no_user_char",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(response.status_code, 200)

    def test_get_logs(self):
        self.make_superuser()

        with patch("tech.router.DockerContainer") as container_mock:
            with patch("tech.router.container_names") as container_list_mock:

                container_list_mock.return_value = ["app_container"]
                container = Mock()
                container_mock.return_value = container

                container.log_entries.return_value = [
                    DockerLogEntry("app_container", "123", "Test logs"),
                    DockerLogEntry("app_container", "124", "Line 2"),
                ]

                response = self.client.get(
                    f"{BASE_URL}/containers/app_container/logs",
                    HTTP_AUTHORIZATION=f"Bearer {self.token}",
                )
                self.assertEqual(response.status_code, 200)
                content = response.content.decode("utf-8")
                self.assertIn("app_container", content)
                self.assertIn("Test logs", content)
                self.assertIn("Line 2", content)
