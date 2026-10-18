"""Shared helpers for management commands that copy from production_readonly."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError
from django.db import DatabaseError, connections
from eveuniverse.models import EveType

from eveonline.models import EveCharacter

_LOOPBACK_HOSTS = {"", "localhost", "127.0.0.1", "::1"}
_DEFAULT_PORTS = {"mysql": "3306", "postgresql": "5432"}


def validate_source_alias(source: str, local: str = "default") -> None:
    """Refuse to copy unless source and local are different databases.

    The *_from_production commands read ``source`` and write (and with
    --clear, delete) in ``local``. Comparing alias names is not enough: on a
    host where both aliases reach the same server they would delete the
    rows they are about to copy. So this also compares the configured
    host/port/name, asks both MySQL servers who they are, and only runs
    with DEBUG on (these are local development tools).
    """
    if source not in settings.DATABASES:
        raise CommandError(
            f'Database alias "{source}" is not configured. '
            "Set production_readonly (see app settings / DB_READONLY_*)."
        )
    if source == local:
        raise CommandError("Source and destination must differ.")
    if local not in settings.DATABASES:
        raise CommandError(f'Database alias "{local}" is not configured.')
    if not settings.DEBUG:
        raise CommandError(
            "Production import commands only run with DEBUG=True: they "
            "write into the local database."
        )
    if database_identity(source) == database_identity(local):
        raise CommandError(
            f'"{source}" and "{local}" point at the same database. '
            "Refusing to copy a database into itself."
        )
    source_server = server_identity(source)
    if source_server is not None and source_server == server_identity(local):
        raise CommandError(
            f'"{source}" and "{local}" reach the same database server '
            f"({source_server[0]}:{source_server[1]}/{source_server[2]}). "
            "Refusing to copy a database into itself."
        )


def database_identity(alias: str) -> tuple:
    """Where an alias points, from its settings, normalised for comparing."""
    database = settings.DATABASES[alias]
    engine = database.get("ENGINE", "")
    vendor = engine.rsplit(".", 1)[-1]
    name = str(database.get("NAME") or "")
    if vendor == "sqlite3":
        if name and name != ":memory:":
            name = str(Path(name).resolve())
        return (vendor, name)
    host = str(database.get("HOST") or "").strip().lower()
    if host in _LOOPBACK_HOSTS:
        host = "localhost"
    port = str(database.get("PORT") or "").strip()
    port = port or _DEFAULT_PORTS.get(vendor, "")
    return (vendor, host, port, name)


def server_identity(alias: str) -> tuple | None:
    """Ask a MySQL server for its hostname, port and current database.

    Two aliases with different HOST strings (an IP and a DNS name, a proxy)
    can still reach the same server; this catches that. Returns None for
    other database vendors.
    """
    connection = connections[alias]
    if connection.vendor != "mysql":
        return None
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT @@hostname, @@port, DATABASE()")
            row = cursor.fetchone()
    except DatabaseError as exc:
        raise CommandError(
            f'Could not identify the database server behind "{alias}": '
            f"{exc}"
        ) from exc
    return tuple(str(value) for value in row)


def assert_local_has_eve_types(
    eve_type_ids: set[int],
    local: str = "default",
    *,
    hint: str = "Load eveuniverse data locally first.",
) -> None:
    missing = missing_eve_type_ids(eve_type_ids, local)
    if missing:
        raise CommandError(
            "Local default DB is missing EveType rows for EVE type IDs: "
            f"{missing[:20]}{'…' if len(missing) > 20 else ''}. "
            f"{hint}"
        )


def missing_eve_type_ids(
    eve_type_ids: set[int], local: str = "default"
) -> list[int]:
    if not eve_type_ids:
        return []
    existing = set(
        EveType.objects.using(local)
        .filter(pk__in=eve_type_ids)
        .values_list("pk", flat=True)
    )
    return sorted(eve_type_ids - existing)


def fetch_eve_types_from_esi(type_ids: list[int]) -> None:
    for type_id in type_ids:
        EveType.objects.update_or_create_esi(
            id=type_id, include_children=False
        )


def ensure_character_from_prod(
    character_id: int,
    prod_char: EveCharacter | None,
    local: str = "default",
) -> EveCharacter:
    """Upsert a minimal local EveCharacter keyed by ESI character_id."""
    existing = (
        EveCharacter.objects.using(local)
        .filter(character_id=character_id)
        .first()
    )
    if existing:
        if (
            prod_char
            and prod_char.character_name
            and not existing.character_name
        ):
            existing.character_name = prod_char.character_name
            existing.save(
                using=local,
                update_fields=["character_name", "updated_at"],
            )
        return existing

    name = ""
    corporation_id = None
    alliance_id = None
    faction_id = None
    if prod_char:
        name = prod_char.character_name or ""
        corporation_id = prod_char.corporation_id
        alliance_id = prod_char.alliance_id
        faction_id = prod_char.faction_id

    return EveCharacter.objects.using(local).create(
        character_id=character_id,
        character_name=name,
        corporation_id=corporation_id,
        alliance_id=alliance_id,
        faction_id=faction_id,
        token_id=None,
        user_id=None,
    )
