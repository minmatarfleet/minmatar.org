"""The *_from_production commands refuse to copy a database into itself."""

from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase, override_settings

from eveonline.helpers import production_import
from eveonline.helpers.production_import import (
    database_identity,
    server_identity,
    validate_source_alias,
)
from posts.models import EveTag


def _mysql(host="127.0.0.1", port="3306", name="minmatar", user="root"):
    return {
        "ENGINE": "django.db.backends.mysql",
        "HOST": host,
        "PORT": port,
        "NAME": name,
        "USER": user,
    }


def _databases(source, local):
    return {"default": local, "production_readonly": source}


@patch.object(production_import, "server_identity", return_value=None)
class ValidateSourceAliasTestCase(SimpleTestCase):
    @override_settings(DEBUG=True)
    def test_unconfigured_source(self, server):
        with self.assertRaisesMessage(CommandError, "not configured"):
            validate_source_alias("nope")

    @override_settings(DEBUG=True)
    def test_same_alias(self, server):
        with self.assertRaisesMessage(CommandError, "must differ"):
            validate_source_alias("default", "default")

    @override_settings(
        DEBUG=False,
        DATABASES=_databases(_mysql(host="prod.example"), _mysql()),
    )
    def test_refuses_without_debug(self, server):
        with self.assertRaisesMessage(CommandError, "DEBUG=True"):
            validate_source_alias("production_readonly")

    @override_settings(
        DEBUG=True,
        DATABASES=_databases(
            _mysql(host="db.example", user="readonly"),
            _mysql(host="DB.example", port="", user="root"),
        ),
    )
    def test_refuses_same_host_and_name_under_another_user(self, server):
        with self.assertRaisesMessage(CommandError, "same database"):
            validate_source_alias("production_readonly")

    @override_settings(
        DEBUG=True,
        DATABASES=_databases(_mysql(host="localhost"), _mysql(host="")),
    )
    def test_loopback_spellings_are_the_same_host(self, server):
        with self.assertRaisesMessage(CommandError, "same database"):
            validate_source_alias("production_readonly")

    @override_settings(
        DEBUG=True,
        DATABASES=_databases(_mysql(host="prod.example"), _mysql()),
    )
    def test_allows_a_different_database(self, server):
        validate_source_alias("production_readonly")

    @override_settings(
        DEBUG=True,
        DATABASES=_databases(_mysql(name="minmatar"), _mysql(name="dev")),
    )
    def test_same_server_other_schema_is_allowed(self, server):
        validate_source_alias("production_readonly")

    @override_settings(
        DEBUG=True,
        DATABASES=_databases(_mysql(host="10.0.0.5"), _mysql(host="db")),
    )
    def test_refuses_when_the_servers_report_the_same_identity(self, server):
        server.return_value = ("db-1", "3306", "minmatar")
        with self.assertRaisesMessage(CommandError, "same database server"):
            validate_source_alias("production_readonly")

    @override_settings(
        DEBUG=True,
        DATABASES=_databases(_mysql(host="10.0.0.5"), _mysql(host="db")),
    )
    def test_allows_servers_with_different_identities(self, server):
        server.side_effect = [
            ("prod-db", "3306", "minmatar"),
            ("dev-db", "3306", "minmatar"),
        ]
        validate_source_alias("production_readonly")


class DatabaseIdentityTestCase(SimpleTestCase):
    @override_settings(
        DATABASES={
            "a": {"ENGINE": "django.db.backends.sqlite3", "NAME": "x.db"},
            "b": {"ENGINE": "django.db.backends.sqlite3", "NAME": "./x.db"},
        }
    )
    def test_sqlite_paths_are_resolved(self):
        self.assertEqual(database_identity("a"), database_identity("b"))


class ServerIdentityTestCase(SimpleTestCase):
    def _connection(self, vendor="mysql", row=None, error=None):
        cursor = MagicMock()
        cursor.__enter__.return_value = cursor
        cursor.fetchone.return_value = row
        if error:
            cursor.execute.side_effect = error
        connection = MagicMock(vendor=vendor)
        connection.cursor.return_value = cursor
        return connection

    def test_not_mysql(self):
        with patch.object(
            production_import,
            "connections",
            {"x": self._connection(vendor="sqlite")},
        ):
            self.assertIsNone(server_identity("x"))

    def test_mysql_identity(self):
        connection = self._connection(row=("db-1", 3306, "minmatar"))
        with patch.object(production_import, "connections", {"x": connection}):
            self.assertEqual(
                ("db-1", "3306", "minmatar"), server_identity("x")
            )

    def test_query_failure_refuses(self):
        connection = self._connection(error=DatabaseError("denied"))
        with patch.object(production_import, "connections", {"x": connection}):
            with self.assertRaisesMessage(CommandError, "Could not identify"):
                server_identity("x")


class ImportCommandSelfCopyTestCase(TestCase):
    """--clear never runs when both aliases are the same database."""

    def test_import_with_clear_refuses_to_copy_default_into_itself(self):
        EveTag.objects.create(tag="kept")
        same_as_default = dict(settings.DATABASES["default"])
        with override_settings(
            DEBUG=True,
            DATABASES={
                "default": settings.DATABASES["default"],
                "production_readonly": same_as_default,
            },
        ):
            with self.assertRaisesMessage(CommandError, "same database"):
                call_command("import_posts_from_production", "--clear")
        self.assertTrue(EveTag.objects.filter(tag="kept").exists())
