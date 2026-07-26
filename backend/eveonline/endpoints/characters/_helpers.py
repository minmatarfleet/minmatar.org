"""Shared helpers for character endpoints."""

import logging
from typing import List

from django.contrib.auth.models import User
from django.shortcuts import redirect
from esi.models import Token

from app.errors import create_error_id
from audit.models import AuditEntry
from applications.models import EveCorporationApplication
from eveonline.endpoints.characters.schemas import UserCharacter
from eveonline.helpers.characters import (
    merge_scope_groups,
    set_primary_character,
    user_primary_character,
)
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterLog,
    EveCharacterTag,
    EveCorporation,
)
from eveonline.scopes import (
    scope_group,
    TokenType,
    token_type_str,
)
from groups.helpers import PEOPLE_TEAM, TECH_TEAM, user_in_team

logger = logging.getLogger(__name__)


def can_manage_tags(user: User, character: EveCharacter) -> bool:
    if character.user == user:
        return True
    if user.is_superuser:
        return True
    if user_in_team(user, TECH_TEAM) or user_in_team(user, PEOPLE_TEAM):
        return True
    return False


def is_primary(char: EveCharacter, primary: EveCharacter | None) -> bool:
    return bool(primary and char == primary)


def user_has_pending_or_rejected_application(user) -> bool:
    return (
        EveCorporationApplication.objects.filter(user=user)
        .exclude(status="accepted")
        .exists()
    )


def build_character_response(char: EveCharacter, primary: EveCharacter | None):
    item = UserCharacter(
        character_id=char.character_id,
        character_name=char.character_name,
        is_primary=is_primary(char, primary),
        flags=[],
    )
    try:
        if char.corporation_id is not None:
            item.corp_id = char.corporation_id
            item.corp_name = (
                EveCorporation.objects.filter(
                    corporation_id=char.corporation_id
                )
                .values_list("name", flat=True)
                .first()
                or ""
            )
        if char.alliance_id is not None:
            item.alliance_id = char.alliance_id
            item.alliance_name = (
                EveAlliance.objects.filter(alliance_id=char.alliance_id)
                .values_list("name", flat=True)
                .first()
                or ""
            )
        if item.is_primary and item.alliance_id != 99011978:
            if not user_has_pending_or_rejected_application(char.user):
                item.flags.append("MAIN_NOT_IN_FL33T")
        if getattr(char, "tag_count", 0) == 0:
            item.flags.append("NO_TAGS")
        level = char.esi_token_level or (
            scope_group(char.token) if char.token else None
        )
        if not level:
            item.flags.append("NO_TOKEN_LEVEL")
        if level:
            item.esi_token = token_type_str(level)
            if char.esi_suspended:
                item.token_status = "SUSPENDED"
                item.flags.append("ESI_SUSPENDED")
            else:
                item.token_status = "ACTIVE"
    except Exception as e:
        logger.error(
            "Error enriching character %s, %s", char.character_name, e
        )
        item.flags.append("DATA_ERROR")
    return item


def add_tags_for_character(
    character: EveCharacter, tag_ids: List[int]
) -> None:
    for tag_id in tag_ids:
        EveCharacterTag.objects.get_or_create(
            character=character,
            tag_id=tag_id,
        )


# --- Add character (SSO) callback helpers ---


def set_or_remove_session_value(request, key, value):
    if value:
        request.session[key] = value
    else:
        request.session.pop(key, None)


def check_add_character_session_match(request, token):
    if "add_character_id" not in request.session:
        return None
    if str(token.character_id) == request.session["add_character_id"]:
        return None
    error_id = create_error_id()
    logger.error(
        "Incorrect character in token refresh, %s != %s (%s)",
        str(token.character_id),
        request.session["add_character_id"],
        error_id,
    )
    return redirect(
        request.session["redirect_url"]
        + "?error=wrong_character&error_id="
        + error_id
    )


def fixup_character_token_level(character, token_count):
    if not character.esi_token_level:
        if token_count == 1 and not character.token:
            character.token = Token.objects.filter(
                character_id=character.character_id
            ).first()
        if character.token:
            character.esi_token_level = scope_group(character.token)
            character.save(update_fields=["esi_token_level"])


def _linked_token_level(token: Token, fallback_group: str) -> str:
    if token.scopes.exists():
        return scope_group(token) or fallback_group
    return fallback_group


def _delete_other_character_tokens(
    character_id: int, keep_token: Token
) -> None:
    Token.objects.filter(character_id=character_id).exclude(
        pk=keep_token.pk
    ).delete()


def apply_token_to_existing_character(character, token, token_type):
    group_name = token_type_str(token_type)
    character.esi_scope_groups = merge_scope_groups(
        getattr(character, "esi_scope_groups", None),
        group_name,
    )

    new_scope_count = token.scopes.count()
    old_token = character.token
    level = _linked_token_level(token, group_name)

    if (
        old_token
        and old_token != token
        and new_scope_count >= old_token.scopes.count()
    ):
        logger.info("Replacing token for %s", token.character_id)
        character.token = token
        character.user = token.user
        character.esi_token_level = level
        character.esi_suspended = False
        character.save()
        _delete_other_character_tokens(character.character_id, token)
    elif not old_token:
        character.token = token
        character.user = token.user
        character.esi_token_level = level
        character.esi_suspended = False
        character.save()
        _delete_other_character_tokens(character.character_id, token)
    elif old_token == token:
        character.esi_token_level = level
        character.esi_suspended = False
        character.save()
        _delete_other_character_tokens(character.character_id, token)
    elif token != old_token:
        token.delete()
        character.save(update_fields=["esi_scope_groups"])


def maybe_populate_ceo_corporation(character, token_type):
    if token_type not in (
        TokenType.DIRECTOR,
        TokenType.MARKET,
        TokenType.EXECUTOR,
    ):
        return
    if not character.corporation_id:
        return
    corp = EveCorporation.objects.filter(
        corporation_id=character.corporation_id
    ).first()
    if corp:
        corp.populate()


def handle_add_character_esi_callback(request, token, token_type):
    wrong_char_redirect = check_add_character_session_match(request, token)
    if wrong_char_redirect is not None:
        return wrong_char_redirect
    if EveCharacter.objects.filter(character_id=token.character_id).exists():
        character = EveCharacter.objects.get(character_id=token.character_id)
        apply_token_to_existing_character(character, token, token_type)
    else:
        character = EveCharacter.objects.create(
            character_id=token.character_id,
            character_name=token.character_name,
            esi_token_level=token_type_str(token_type),
            esi_scope_groups=[token_type_str(token_type)],
            token=token,
            user=token.user,
        )
        AuditEntry.objects.create(
            user=request.user,
            character=character,
            category="character_added",
            summary=f"User {request.user.username} added character {character.character_name}",
        )
    EveCharacterLog.objects.create(
        username=request.user.username,
        character_name=character.character_name,
    )
    if user_primary_character(request.user) is None:
        set_primary_character(request.user, character)
    maybe_populate_ceo_corporation(character, token_type)
    return redirect(request.session["redirect_url"])
