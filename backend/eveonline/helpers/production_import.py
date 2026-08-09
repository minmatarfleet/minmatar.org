"""Shared helpers for management commands that copy from production_readonly."""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import CommandError
from eveuniverse.models import EveType


def validate_source_alias(source: str, local: str = "default") -> None:
    if source not in settings.DATABASES:
        raise CommandError(
            f'Database alias "{source}" is not configured. '
            "Set production_readonly (see app settings / DB_READONLY_*)."
        )
    if source == local:
        raise CommandError("Source and destination must differ.")


def assert_local_has_eve_types(
    eve_type_ids: set[int],
    local: str = "default",
    *,
    hint: str = "Load eveuniverse data locally first.",
) -> None:
    if not eve_type_ids:
        return
    existing = set(
        EveType.objects.using(local)
        .filter(pk__in=eve_type_ids)
        .values_list("pk", flat=True)
    )
    missing = sorted(eve_type_ids - existing)
    if missing:
        raise CommandError(
            "Local default DB is missing EveType rows for EVE type IDs: "
            f"{missing[:20]}{'…' if len(missing) > 20 else ''}. "
            f"{hint}"
        )
