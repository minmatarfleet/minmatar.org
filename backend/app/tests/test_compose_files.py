"""
The compose files must parse the way docker compose reads them.

An unquoted list entry containing ": " (``- KEY=Help: url``) is a YAML map,
not a string, and ``docker compose`` then refuses the whole file. On the
production host that fails the deploy at the image build step.
"""

from pathlib import Path
from unittest import skipUnless

import yaml
from django.conf import settings
from django.test import SimpleTestCase

REPO = Path(settings.BASE_DIR).parent
COMPOSE_FILES = sorted(REPO.glob("docker-compose*.yml"))

# Service keys whose list form must hold only strings.
STRING_LIST_KEYS = (
    "environment",
    "labels",
    "ports",
    "volumes",
    "extra_hosts",
    "env_file",
    "command",
    "entrypoint",
)


def non_string_entries(compose: dict):
    for name, service in (compose.get("services") or {}).items():
        for key in STRING_LIST_KEYS:
            value = service.get(key)
            if isinstance(value, list):
                for index, entry in enumerate(value):
                    if not isinstance(entry, (str, int)):
                        yield f"services.{name}.{key}[{index}]: {entry!r}"
        build = service.get("build")
        args = build.get("args") if isinstance(build, dict) else None
        if isinstance(args, list):
            for index, entry in enumerate(args):
                if not isinstance(entry, str):
                    yield f"services.{name}.build.args[{index}]: {entry!r}"


class ComposeFilesTestCase(SimpleTestCase):
    @skipUnless(COMPOSE_FILES, "compose files are outside the image")
    def test_list_entries_are_strings(self):
        for path in COMPOSE_FILES:
            with self.subTest(file=path.name):
                compose = yaml.safe_load(path.read_text())
                problems = list(non_string_entries(compose))
                self.assertEqual(
                    problems,
                    [],
                    f"{path.name}: quote these entries (an unquoted "
                    "': ' makes YAML read them as maps)",
                )


class VoiceAuthRestartTestCase(SimpleTestCase):
    """voice-auth must come back on its own when its main loop hangs.

    Docker never restarts a container that is only unhealthy. voice-auth's
    watchdog exits the process instead (voice/voice_auth/health.py), which
    needs ``restart: always``; the healthcheck still flags it meanwhile.
    """

    @skipUnless(
        (REPO / "docker-compose-prod.yml").exists(),
        "compose files are outside the image",
    )
    def test_voice_auth_restarts_and_has_a_healthcheck_with_retries(self):
        compose = yaml.safe_load(
            (REPO / "docker-compose-prod.yml").read_text()
        )
        service = compose["services"]["voice-auth"]
        self.assertEqual(service.get("restart"), "always")
        healthcheck = service.get("healthcheck") or {}
        self.assertIn("/health", " ".join(healthcheck.get("test") or []))
        self.assertGreaterEqual(int(healthcheck.get("retries", 0)), 2)
