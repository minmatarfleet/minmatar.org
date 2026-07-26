"""Sync access lists from ESI for the executor character."""

import logging

import requests
from django.contrib.auth import get_user_model
from django.utils import timezone
from esi.models import Token

from access_lists.models import (
    AccessLevel,
    EntityType,
    EveAccessList,
    EveAccessListMember,
)
from eveonline.client import ESI_BASE_URL, esi_for
from eveonline.helpers.db_sync import replace_with_bulk_create
from eveonline.models import EveAlliance, EveCharacter, EveCorporation

logger = logging.getLogger(__name__)

User = get_user_model()

DEFAULT_EXECUTOR_CHARACTER_NAME = "BearThatFarms"
SCOPE_ACCESS_LISTS = ["esi-access.read_lists.v1"]


def get_executor_character(
    character_name: str = DEFAULT_EXECUTOR_CHARACTER_NAME,
) -> EveCharacter | None:
    """
    Resolve the executor character used for ACL sync.
    Matches by character name, then linked username (e.g. bearthatfarms).
    """
    character = EveCharacter.objects.filter(
        character_name__icontains=character_name
    ).first()
    if character:
        return character

    username_hint = character_name.lower().replace(" ", "")
    user = User.objects.filter(username__icontains=username_hint).first()
    if user:
        return EveCharacter.objects.filter(user=user).first()
    return None


def _entity_name(entity_type: str, entity_id: int) -> str:
    if entity_type == EntityType.CHARACTER:
        name = (
            EveCharacter.objects.filter(character_id=entity_id)
            .values_list("character_name", flat=True)
            .first()
        )
        return name or ""
    if entity_type == EntityType.CORPORATION:
        name = (
            EveCorporation.objects.filter(corporation_id=entity_id)
            .values_list("name", flat=True)
            .first()
        )
        return name or ""
    if entity_type == EntityType.ALLIANCE:
        name = (
            EveAlliance.objects.filter(alliance_id=entity_id)
            .values_list("name", flat=True)
            .first()
        )
        return name or ""
    return ""


def _resolve_entity_names(members: list[EveAccessListMember]) -> None:
    unresolved = [member for member in members if not member.entity_name]
    if not unresolved:
        return

    try:
        response = requests.post(
            f"{ESI_BASE_URL}/universe/names/",
            json=[member.entity_id for member in unresolved],
            timeout=30,
        )
    except Exception:
        logger.exception("Failed to resolve access list entity names from ESI")
        return

    if response.status_code >= 400:
        logger.warning(
            "Universe names lookup failed with status %s",
            response.status_code,
        )
        return

    names_by_id = {item["id"]: item["name"] for item in response.json()}
    for member in unresolved:
        member.entity_name = names_by_id.get(member.entity_id, "")


def _members_from_detail(detail: dict) -> list[EveAccessListMember]:
    membership = detail.get("membership") or {}
    members: list[EveAccessListMember] = []

    for entry in membership.get("characters") or []:
        members.append(
            EveAccessListMember(
                entity_type=EntityType.CHARACTER,
                entity_id=entry["character_id"],
                access=entry["access"],
            )
        )
    for entry in membership.get("corporations") or []:
        members.append(
            EveAccessListMember(
                entity_type=EntityType.CORPORATION,
                entity_id=entry["corporation_id"],
                access=entry["access"],
            )
        )
    for entry in membership.get("alliances") or []:
        members.append(
            EveAccessListMember(
                entity_type=EntityType.ALLIANCE,
                entity_id=entry["alliance_id"],
                access=entry["access"],
            )
        )

    for member in members:
        if member.access not in AccessLevel.values:
            logger.warning(
                "Unknown access level %r for %s %s",
                member.access,
                member.entity_type,
                member.entity_id,
            )
        member.entity_name = _entity_name(member.entity_type, member.entity_id)

    _resolve_entity_names(members)
    return members


def upsert_access_list(
    owner_character: EveCharacter,
    access_list_id: int,
    detail: dict,
) -> EveAccessList:
    membership = detail.get("membership") or {}
    access_list, _ = EveAccessList.objects.update_or_create(
        access_list_id=access_list_id,
        defaults={
            "name": detail.get("name") or f"ACL {access_list_id}",
            "description": detail.get("description") or "",
            "allow_everyone": bool(membership.get("allow_everyone")),
            "owner_character": owner_character,
            "last_synced_at": timezone.now(),
        },
    )

    members = _members_from_detail(detail)
    for member in members:
        member.access_list = access_list

    replace_with_bulk_create(
        delete_queryset=EveAccessListMember.objects.filter(
            access_list=access_list
        ),
        instances=members,
    )
    return access_list


def sync_access_lists_for_character(
    character: EveCharacter,
) -> dict[str, int | str | bool]:
    """Pull all ACLs visible to the character and store them locally."""
    esi = esi_for(character)
    listing = esi.get_character_access_lists()
    if not listing.success():
        return {
            "success": False,
            "error": listing.error_text(),
        }

    payload = listing.results() or {}
    access_list_ids = [
        item["id"] for item in payload.get("access_lists") or []
    ]

    synced = 0
    for access_list_id in access_list_ids:
        detail_response = esi.get_character_access_list_detail(access_list_id)
        if not detail_response.success():
            logger.warning(
                "Failed to fetch ACL %s for %s: %s",
                access_list_id,
                character.character_name,
                detail_response.error_text(),
            )
            continue
        upsert_access_list(
            character,
            access_list_id,
            detail_response.results() or {},
        )
        synced += 1

    stale_queryset = EveAccessList.objects.filter(
        owner_character=character
    ).exclude(access_list_id__in=access_list_ids)
    removed = stale_queryset.count()
    stale_queryset.delete()

    return {
        "success": True,
        "listed": len(access_list_ids),
        "synced": synced,
        "removed": removed,
    }


def sync_executor_access_lists(
    character_name: str = DEFAULT_EXECUTOR_CHARACTER_NAME,
) -> dict[str, int | str | bool]:
    """Sync ACLs from the configured executor character."""
    character = get_executor_character(character_name)
    if not character:
        return {
            "success": False,
            "error": f"Executor character '{character_name}' not found",
        }
    if character.esi_suspended:
        return {
            "success": False,
            "error": f"{character.character_name} ESI token is suspended",
        }

    if not Token.get_token(character.character_id, SCOPE_ACCESS_LISTS):
        return {
            "success": False,
            "error": (
                f"{character.character_name} has no token with "
                f"{SCOPE_ACCESS_LISTS[0]}"
            ),
        }

    return sync_access_lists_for_character(character)
