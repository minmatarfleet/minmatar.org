"""Developer-only switches can never turn on with DEBUG off."""

import importlib
import os
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings

from app import settings_env
from app.dev_switches import fake_login_user_id, mock_esi_enabled
from eveonline.client import EsiClient, esi_for

_SWITCHES = {
    "FAKE_LOGIN_USER_ID": "1",
    "MOCK_ESI": "True",
    "SETUP_TEST_DATA": "True",
}


def _resolve(environ):
    """Re-evaluate app/settings_env.py under the given environment."""
    with patch.dict(os.environ, environ, clear=True):
        module = importlib.reload(settings_env)
        resolved = {
            name: getattr(module, name)
            for name in (*_SWITCHES, "DEBUG", "SESSION_ENGINE")
            if hasattr(module, name)
        }
    importlib.reload(settings_env)
    return resolved


class SettingsEnvSwitchesTestCase(SimpleTestCase):
    def test_switches_are_off_without_debug_even_when_set(self):
        for debug in ({}, {"DEBUG": "False"}, {"DEBUG": "true"}):
            resolved = _resolve({**_SWITCHES, **debug})
            self.assertFalse(resolved["DEBUG"])
            self.assertIsNone(resolved["FAKE_LOGIN_USER_ID"])
            self.assertFalse(resolved["MOCK_ESI"])
            self.assertFalse(resolved["SETUP_TEST_DATA"])
            self.assertNotIn("SESSION_ENGINE", resolved)

    def test_switches_work_with_debug(self):
        resolved = _resolve({**_SWITCHES, "DEBUG": "True"})
        self.assertEqual("1", resolved["FAKE_LOGIN_USER_ID"])
        self.assertTrue(resolved["MOCK_ESI"])
        self.assertTrue(resolved["SETUP_TEST_DATA"])

    def test_false_strings_are_false(self):
        resolved = _resolve(
            {
                "DEBUG": "True",
                "FAKE_LOGIN_USER_ID": " ",
                "MOCK_ESI": "False",
                "SETUP_TEST_DATA": "0",
            }
        )
        self.assertIsNone(resolved["FAKE_LOGIN_USER_ID"])
        self.assertFalse(resolved["MOCK_ESI"])
        self.assertFalse(resolved["SETUP_TEST_DATA"])

    def test_old_trailing_space_keys_do_nothing(self):
        resolved = _resolve(
            {
                "DEBUG": "True",
                "FAKE_LOGIN_USER_ID ": "1",
                "MOCK_ESI ": "True",
            }
        )
        self.assertIsNone(resolved["FAKE_LOGIN_USER_ID"])
        self.assertFalse(resolved["MOCK_ESI"])


class EnvHelpersTestCase(SimpleTestCase):
    def test_env_bool(self):
        cases = {
            "1": True,
            "true": True,
            "TRUE": True,
            "yes": True,
            "on": True,
            "0": False,
            "False": False,
            "no": False,
            "anything": False,
        }
        for raw, expected in cases.items():
            with patch.dict(os.environ, {"X_FLAG": raw}):
                self.assertIs(expected, settings_env.env_bool("X_FLAG"), raw)
        with patch.dict(os.environ, {"X_FLAG": "  "}):
            self.assertTrue(settings_env.env_bool("X_FLAG", True))

    def test_env_int_and_str_treat_blank_as_unset(self):
        with patch.dict(os.environ, {"X_INT": "", "X_STR": " "}):
            self.assertEqual(7, settings_env.env_int("X_INT", 7))
            self.assertEqual("d", settings_env.env_str("X_STR", "d"))
        with patch.dict(os.environ, {"X_INT": "42", "X_STR": "v"}):
            self.assertEqual(42, settings_env.env_int("X_INT", 7))
            self.assertEqual("v", settings_env.env_str("X_STR", "d"))


class ReadonlyDatabaseTestCase(SimpleTestCase):
    def test_not_defined_without_user_and_host(self):
        for environ in (
            {},
            {"DB_READONLY_USER": "ro"},
            {"DB_READONLY_HOST": "db.example"},
        ):
            with patch.dict(os.environ, environ, clear=True):
                self.assertIsNone(settings_env.readonly_database_from_env())

    def test_defined_from_env_in_read_only_mode(self):
        environ = {
            "DB_READONLY_USER": "ro",
            "DB_READONLY_PASSWORD": "pw",
            "DB_READONLY_HOST": "db.example",
        }
        with patch.dict(os.environ, environ, clear=True):
            database = settings_env.readonly_database_from_env()
        self.assertEqual("ro", database["USER"])
        self.assertEqual("db.example", database["HOST"])
        self.assertEqual("minmatar", database["NAME"])
        self.assertEqual("3306", database["PORT"])
        self.assertEqual(
            "SET SESSION TRANSACTION READ ONLY",
            database["OPTIONS"]["init_command"],
        )


class RuntimeSwitchesTestCase(SimpleTestCase):
    @override_settings(DEBUG=False, FAKE_LOGIN_USER_ID="1", MOCK_ESI=True)
    def test_off_without_debug(self):
        self.assertIsNone(fake_login_user_id())
        self.assertFalse(mock_esi_enabled())

    @override_settings(DEBUG=True, FAKE_LOGIN_USER_ID="1", MOCK_ESI=True)
    def test_on_with_debug(self):
        self.assertEqual("1", fake_login_user_id())
        self.assertTrue(mock_esi_enabled())

    @override_settings(DEBUG=True, FAKE_LOGIN_USER_ID="", MOCK_ESI=False)
    def test_blank_is_off(self):
        self.assertIsNone(fake_login_user_id())
        self.assertFalse(mock_esi_enabled())

    @override_settings(DEBUG=False, MOCK_ESI=True)
    def test_esi_for_uses_real_client_without_debug(self):
        self.assertIsInstance(esi_for(None), EsiClient)


class FakeLoginEndpointsTestCase(TestCase):
    """The login endpoints ignore FAKE_LOGIN_USER_ID unless DEBUG is on."""

    redirect = "https://my.minmatar.org/auth/login"

    def setUp(self):
        self.user = User.objects.create_user(username="fake_target")

    def _assert_not_faked(self, response):
        self.assertEqual(302, response.status_code)
        self.assertNotIn("token=", response.url)
        self.assertNotIn("/admin", response.url)

    def test_login_endpoints_ignore_fake_user_without_debug(self):
        with override_settings(
            DEBUG=False, FAKE_LOGIN_USER_ID=str(self.user.id)
        ):
            self._assert_not_faked(
                self.client.get(
                    "/api/users/login", {"redirect_url": self.redirect}
                )
            )
            self.assertIn(
                "discord.com",
                self.client.get(
                    "/api/users/login", {"redirect_url": self.redirect}
                ).url,
            )
            self._assert_not_faked(self.client.get("/oauth2/login/"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_superuser)
        self.assertFalse(self.user.is_staff)

    def test_eve_login_ignores_fake_user_without_debug(self):
        with override_settings(
            DEBUG=False, FAKE_LOGIN_USER_ID=str(self.user.id)
        ):
            response = self.client.get(
                "/api/users/login/eve", {"redirect_url": self.redirect}
            )
        self.assertNotIn("token=", response.url)

    def test_fake_login_works_with_debug(self):
        with override_settings(
            DEBUG=True, FAKE_LOGIN_USER_ID=str(self.user.id)
        ):
            response = self.client.get(
                "/api/users/login", {"redirect_url": self.redirect}
            )
        self.assertEqual(302, response.status_code)
        self.assertTrue(response.url.startswith(f"{self.redirect}?token="))
