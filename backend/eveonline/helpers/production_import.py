"""Shared helpers for management commands that copy from production_readonly."""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import CommandError
from eveuniverse.models import EveType

from eveonline.models import EveCharacter


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
