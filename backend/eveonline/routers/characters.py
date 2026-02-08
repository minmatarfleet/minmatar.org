import json
import logging
import datetime
from typing import List, Optional

from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.db.models import Count
from esi.decorators import token_required
from esi.models import Token
from ninja import Router
from pydantic import BaseModel

from app.errors import ErrorResponse, create_error_id
from authentication import AuthBearer
from audit.models import AuditEntry
from applications.models import EveCorporationApplication
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterAsset,
    EveCharacterLog,
    EveCharacterSkillset,
    EveCharacterTag,
    EveCorporation,
    EveTag,
)
from eveonline.scopes import (
    TokenType,
    scopes_for,
    scopes_for_groups,
    scope_group,
    token_type_str,
    scope_names,
)
from eveonline.helpers.characters import (
    user_primary_character,
    user_characters,
    character_primary,
    set_primary_character,
    character_desired_scopes,
)

from groups.helpers import PEOPLE_TEAM, TECH_TEAM, user_in_team
from discord.models import DiscordUser

logger = logging.getLogger(__name__)

router = Router(tags=["Characters"])


class BasicCharacterResponse(BaseModel):
    character_id: int
    character_name: str


class CharacterResponse(BasicCharacterResponse):
    primary_character_id: Optional[int] = None
    primary_character_name: Optional[str] = None


class CharacterSkillsetResponse(BaseModel):
    name: str
    progress: float
    missing_skills: List[str]


class CharacterAssetResponse(BaseModel):
    type_id: int
    type_name: str
    location_id: int
    location_name: str


class UserCharacter(BaseModel):
    """Summary of a player's character"""

    character_id: int
    character_name: str
    is_primary: bool
    corp_id: Optional[int] = None
    corp_name: Optional[str] = None
    alliance_id: Optional[int] = None
    alliance_name: Optional[str] = None
    esi_token: Optional[str] = None
    token_status: Optional[str] = None
    flags: List[str] = []


class UserCharacterResponse(BaseModel):
    user_id: int
    user_name: str
    discord_id: str
    characters: List[UserCharacter]


class CharacterTokenInfo(BaseModel):
    """Information about a character's ESI token"""

    id: str
    created: datetime.datetime
    expires: datetime.datetime
    can_refresh: bool
    owner_hash: str
    scopes: List[str]
    requested_level: str
    requested_count: int
    actual_level: str
    actual_count: int
    token_state: str


class CharacterTagResponse(BaseModel):
    id: int
    title: str
    description: str
    image_name: Optional[str] = None


@router.get(
    "",
    summary="Get characters",
    auth=AuthBearer(),
    response={200: List[BasicCharacterResponse], 404: ErrorResponse},
)
def get_characters(request, primary_character_id: int = None):
    if primary_character_id:
        if not EveCharacter.objects.filter(
            character_id=primary_character_id
        ).exists():
            return 404, ErrorResponse(detail="Primary character not found")
        character = EveCharacter.objects.get(character_id=primary_character_id)
        character_user = character.token.user
        characters = user_characters(character_user)
    else:
        characters = user_characters(request.user)
    response = []
    for character in characters:
        response.append(
            {
                "character_id": character.character_id,
                "character_name": character.character_name,
            }
        )
    return response


@router.get(
    "/tags",
    summary="Get possible tags for characters",
    response={
        200: List[CharacterTagResponse],
    },
)
def get_available_tags(request):
    tags = EveTag.objects.all()
    response = []
    for tag in tags:
        response.append(
            CharacterTagResponse(
                id=tag.id,
                title=tag.title,
                description=tag.description,
                image_name=tag.image_name,
            )
        )
    return 200, response


@router.get(
    "/{int:character_id}",
    summary="Get character by ID",
    auth=AuthBearer(),
    response={200: CharacterResponse, 403: ErrorResponse, 404: ErrorResponse},
)
def get_character_by_id(request, character_id: int):
    if not EveCharacter.objects.filter(character_id=character_id).exists():
        return 404, ErrorResponse(detail="Character not found")

    character = EveCharacter.objects.get(character_id=character_id)

    payload = {
        "character_id": character.character_id,
        "character_name": character.character_name,
    }

    if character.token:
        primary_character = character_primary(character)
        if (
            primary_character
            and primary_character.character_id != character_id
        ):
            payload["primary_character_id"] = primary_character.character_id
            payload["primary_character_name"] = (
                primary_character.character_name
            )

    if (
        request.user.has_perm("eveonline.view_evecharacter")
        or request.user.is_superuser
        or character.token
        and character.token.user == request.user
    ):
        return payload
    return 403, {
        "detail": "You do not have permission to view this character."
    }


@router.get(
    "/{int:character_id}/skillsets",
    summary="Get skillsets for character by ID",
    auth=AuthBearer(),
    response={
        200: List[CharacterSkillsetResponse],
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def get_skillsets_for_character_by_id(request, character_id: int):
    if not EveCharacter.objects.filter(character_id=character_id).exists():
        return 404, {"detail": "Character not found."}

    character = EveCharacter.objects.get(character_id=character_id)

    if (
        request.user.has_perm("eveonline.view_evecharacter")
        or character.token
        and character.token.user == request.user
    ):
        skillsets = EveCharacterSkillset.objects.filter(character=character)
        response = []
        for skillset in skillsets:
            response.append(
                {
                    "name": skillset.eve_skillset.name,
                    "progress": skillset.progress,
                    "missing_skills": json.loads(skillset.missing_skills),
                }
            )
        return response

    return 403, {
        "detail": "You do not have permission to view this character."
    }


@router.get(
    "/{int:character_id}/assets",
    summary="Get assets for character by ID",
    auth=AuthBearer(),
    response={
        200: List[CharacterAssetResponse],
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def get_assets_for_character_by_id(request, character_id: int):
    if not EveCharacter.objects.filter(character_id=character_id).exists():
        return 404, {"detail": "Character not found."}

    character = EveCharacter.objects.get(character_id=character_id)

    if (
        request.user.has_perm("eveonline.view_evecharacter")
        or character.token
        and character.token.user == request.user
    ):
        assets = EveCharacterAsset.objects.filter(character=character)
        response = []
        for asset in assets:
            response.append(
                {
                    "type_id": asset.type_id,
                    "type_name": asset.type_name,
                    "location_id": asset.location_id,
                    "location_name": asset.location_name,
                }
            )
        return response

    return 403, {
        "detail": "You do not have permission to view this character."
    }


@router.delete(
    "/{int:character_id}",
    summary="Delete character by ID",
    auth=AuthBearer(),
    response={
        200: None,
        403: ErrorResponse,
        404: ErrorResponse,
        500: ErrorResponse,
    },
)
def delete_character_by_id(request, character_id: int):

    if not EveCharacter.objects.filter(character_id=character_id).exists():
        return 404, {"detail": "Character not found."}
    if not (
        request.user.has_perm("eveonline.delete_evecharacter")
        or Token.objects.filter(
            user=request.user, character_id=character_id
        ).exists()
    ):
        return 403, {
            "detail": "You do not have permission to delete this character."
        }

    # if user is primary character, pick a new primary character if possible
    primary_character = user_primary_character(request.user)
    if primary_character:
        if primary_character.character_id == character_id:
            characters = EveCharacter.objects.filter(
                user=request.user
            ).exclude(character_id=character_id)
            if characters.exists():
                set_primary_character(request.user, characters.first())

    try:
        AuditEntry.objects.create(
            user=request.user,
            category="character_deleted",
            summary=f"User {request.user.username} deleted character {character_id}",
        )
        EveCharacter.objects.filter(character_id=character_id).delete()
        Token.objects.filter(character_id=character_id).delete()
    except Exception as e:
        return 500, ErrorResponse.new(
            "Error deleting character {character_id}", str(e)
        )

    logger.info(
        "User %s deleted character %d", request.user.username, character_id
    )

    return 200, None


@router.put(
    "/primary",
    summary="Set primary character",
    auth=AuthBearer(),
    response={200: None, 403: ErrorResponse, 404: ErrorResponse},
)
def put_primary_character(request, character_id: int):
    character = EveCharacter.objects.filter(character_id=character_id).first()
    if not character:
        return 404, {"detail": f"Character {character_id} not found."}

    if character.user != request.user:
        return 403, {
            "detail": "You do not have permission to set this character as primary."
        }

    set_primary_character(request.user, character)

    return 200, None


@router.get(
    "/primary",
    summary="Get primary character",
    auth=AuthBearer(),
    response={200: BasicCharacterResponse, 404: ErrorResponse},
)
def get_primary_character(request):
    char = user_primary_character(request.user)

    if char is None:
        return 404, {"detail": "Primary character not found."}

    return {
        "character_id": char.character_id,
        "character_name": char.character_name,
    }


def set_or_remove_session_value(request, key, value):
    """Adds a value to the session, or removes it if the value is None."""
    if value:
        request.session[key] = value
    else:
        request.session.pop(key, None)


def _check_add_character_session_match(request, token):
    """Return redirect response if session requested a different character, else None."""
    if "add_character_id" not in request.session:
        return None
    requested_char = request.session["add_character_id"]
    if str(token.character_id) == requested_char:
        return None
    error_id = create_error_id()
    logger.error(
        "Incorrect character in token refresh, %s != %s (%s)",
        str(token.character_id),
        requested_char,
        error_id,
    )
    return redirect(
        request.session["redirect_url"]
        + "?error=wrong_character&error_id="
        + error_id
    )


def _ensure_scope_group_in_list(character, token_type):
    """Add token_type to character.esi_scope_groups if not present."""
    group_str = token_type_str(token_type)
    if not group_str:
        return
    groups = list(character.esi_scope_groups) if character.esi_scope_groups else []
    if group_str not in groups:
        groups.append(group_str)
        character.esi_scope_groups = groups
    # Record first token level only (Basic/Public) when not yet set
    if not character.esi_token_level:
        character.esi_token_level = group_str


def _apply_token_to_existing_character(character, token, token_type):
    """Update an existing character with a new token; handle replace/add/discard cases."""
    if (
        character.token
        and character.token != token
        and len(token.scopes.all()) >= len(character.token.scopes.all())
    ):
        logger.info("Replacing token for %s", token.character_id)
        old_token = character.token
        character.token = token
        character.user = token.user
        character.esi_suspended = False
        _ensure_scope_group_in_list(character, token_type)
        character.save()
        old_token.delete()
    elif not character.token:
        logger.info(
            "Character %s has no token, adding token",
            token.character_id,
        )
        character.token = token
        character.user = token.user
        character.esi_suspended = False
        _ensure_scope_group_in_list(character, token_type)
        character.save()
    elif token != character.token:
        logger.warning(
            "Character %s already has better token, throwing new one away",
            token.character_id,
        )
        token.delete()
    elif token == character.token:
        logger.warning(
            "New token is same as existing one for character %s",
            token.character_id,
        )
    else:
        logger.warning(
            "Unexpected scenario updating token for character %s",
            token.character_id,
        )
    token_count = Token.objects.filter(
        character_id=character.character_id
    ).count()
    if token_count != 1:
        logger.error(
            "Character %d (%s) has %d tokens after update",
            character.character_id,
            character.character_name,
            token_count,
        )
    if not character.token:
        logger.error(
            "Character %d (%s) has no token set after update",
            character.character_id,
            character.character_name,
        )
    fixup_character_token_level(character, token_count)


def _maybe_populate_ceo_corporation(character, token_type):
    """Populate corporation from ESI when token is CEO/MARKET/FREIGHT."""
    if token_type not in (TokenType.CEO, TokenType.MARKET, TokenType.FREIGHT):
        return
    if not character.corporation_id:
        return
    logger.info(
        "Populating CEO token corporation for character %s",
        character.character_id,
    )
    corp = EveCorporation.objects.filter(
        corporation_id=character.corporation_id
    ).first()
    if corp:
        corp.populate()


def handle_add_character_esi_callback(request, token, token_type):
    logger.info(
        "ESI token callback for user %s, %s scopes (%s)",
        token.user.username,
        token.scopes.count(),
        token_type,
    )
    wrong_char_redirect = _check_add_character_session_match(request, token)
    if wrong_char_redirect is not None:
        return wrong_char_redirect

    if EveCharacter.objects.filter(character_id=token.character_id).exists():
        logger.debug(
            "Character %s already exists, updating token",
            token.character_id,
        )
        character = EveCharacter.objects.get(character_id=token.character_id)
        _apply_token_to_existing_character(character, token, token_type)
    else:
        logger.info(
            "Creating new character (%s, %s) with token",
            token.character_id,
            token.character_name,
        )
        group_str = token_type_str(token_type)
        character = EveCharacter.objects.create(
            character_id=token.character_id,
            character_name=token.character_name,
            esi_token_level=group_str,
            esi_scope_groups=[group_str] if group_str else [],
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
        logger.info(
            "Setting primary character %s for user %s",
            character.character_name,
            request.user.username,
        )
        set_primary_character(request.user, character)
    _maybe_populate_ceo_corporation(character, token_type)
    return redirect(request.session["redirect_url"])


@router.get("/add", summary="Add character using EVE Online SSO")
def add_character(
    request,
    redirect_url: str,
    token_type: Optional[TokenType] = None,
    character_id: str = None,
):
    request.session["redirect_url"] = redirect_url
    set_or_remove_session_value(request, "add_character_id", character_id)

    logger.info("Add character with token type %s", token_type)

    if not token_type:
        if character_id:
            char = EveCharacter.objects.get(character_id=character_id)
            if getattr(char, "esi_scope_groups", None):
                try:
                    token_type = TokenType(char.esi_scope_groups[0])
                except (ValueError, TypeError, IndexError):
                    token_type = TokenType.BASIC
            else:
                try:
                    token_type = TokenType(char.esi_token_level or "")
                except (ValueError, TypeError):
                    token_type = TokenType.BASIC
        else:
            token_type = TokenType.BASIC

    if character_id and token_type == TokenType.PUBLIC:
        # Upgrade public tokens to basic when refreshing
        token_type = TokenType.BASIC

    # Upgrade/refresh: request current scopes union new group. New character: just that group.
    if character_id:
        char = EveCharacter.objects.get(character_id=character_id)
        current = scope_names(char.token) if char.token else []
        scopes = sorted(set(current) | set(scopes_for(token_type)))
    else:
        scopes = scopes_for(token_type)

    logger.info(
        "ESI token request for %s (%s), type = %s",
        request.user.username,
        str(character_id),
        token_type,
    )

    @login_required()
    @token_required(scopes=scopes, new=True)
    def wrapped(request, token):
        return handle_add_character_esi_callback(request, token, token_type)

    return wrapped(request)  # pylint: disable=no-value-for-parameter


def fixup_character_token_level(character, token_count):
    if token_count == 1 and not character.token:
        character.token = Token.objects.filter(
            character_id=character.character_id
        ).first()
    if character.token and not character.esi_scope_groups:
        group = scope_group(character.token)
        if group:
            character.esi_scope_groups = [group]
            character.save(update_fields=["esi_scope_groups"])


@router.get(
    "/summary",
    summary="Returns a summary of character information for a user",
    auth=AuthBearer(),
    response={
        200: UserCharacterResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def get_user_characters(
    request, discord_id: int = None, character_name: str = None
) -> UserCharacterResponse:

    if discord_id or character_name:
        # Parameters provided, must be a superuser
        if not request.user.is_superuser:
            return 403, ErrorResponse(detail="Not authorised")

        if discord_id and character_name:
            return 400, ErrorResponse(
                detail="Only 1 query parameter supported"
            )

    if character_name:
        char = EveCharacter.objects.filter(
            character_name=character_name
        ).first()

        if not char:
            return 404, ErrorResponse(detail="No matching character found")

        if not char.user:
            return 400, ErrorResponse.log(
                "Character not linked to a user", char.id
            )

        char_user = char.user

        discord_user = DiscordUser.objects.filter(user=char_user).first()
    elif discord_id:
        discord_user = DiscordUser.objects.filter(id=discord_id).first()

        if not discord_user:
            return 404, ErrorResponse.log(
                "No matching discord user found", discord_id
            )

        char_user = discord_user.user
    else:
        # No parameters provided, only return current user details
        char_user = request.user
        discord_user = DiscordUser.objects.filter(user=char_user).first()

        if not discord_user:
            return 404, ErrorResponse.new("No matching discord user found")

    response = UserCharacterResponse(
        user_id=char_user.id,
        user_name=char_user.username,
        discord_id=str(discord_user.id),
        characters=[],
    )

    primary = user_primary_character(char_user)

    chars = EveCharacter.objects.filter(user=char_user).annotate(
        tag_count=Count("evecharactertag", distinct=True),
    )
    for char in chars.all():
        char_response = build_character_response(char, primary)
        response.characters.append(char_response)

    return response


def is_primary(char: EveCharacter, primary: EveCharacter | None) -> bool:
    # Return an explicit True or False, rather than just a truthy value
    # Pydantic validation fails if I use the expression rather than calling this function
    return bool(primary and char == primary)


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

        if char.tag_count and char.tag_count == 0:
            item.flags.append("NO_TAGS")

        if char.esi_token_level:
            level = char.esi_token_level
        elif char.token:
            level = scope_group(char.token)
        else:
            level = None
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


def user_has_pending_or_rejected_application(user):
    return (
        EveCorporationApplication.objects.filter(user=user)
        .exclude(status="accepted")
        .exists()
    )


@router.get(
    "/{int:character_id}/tokens",
    summary="Get ESI tokens for character by ID",
    auth=AuthBearer(),
    response={
        200: List[CharacterTokenInfo],
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def get_character_tokens(request, character_id: int):
    character = EveCharacter.objects.filter(character_id=character_id).first()
    if not character:
        return 404, ErrorResponse(detail="Character not found")

    is_admin = (
        request.user.is_superuser
        or user_in_team(request.user, PEOPLE_TEAM)
        or user_in_team(request.user, TECH_TEAM)
    )

    response = []

    for token in Token.objects.filter(character_id=character.character_id):
        if is_admin or token.user is request.user:
            scopes = scope_names(token)

            if character.esi_token_level:
                pass

            response.append(
                CharacterTokenInfo(
                    id=str(token.pk),
                    created=token.created,
                    expires=token.expires,
                    can_refresh=token.can_refresh,
                    owner_hash=token.character_owner_hash,
                    scopes=scopes,
                    requested_level=character.esi_token_level,
                    requested_count=len(character_desired_scopes(character)),
                    actual_level=scope_group(token),
                    actual_count=len(scopes),
                    token_state=(
                        "SUSPENDED" if character.esi_suspended else "ACTIVE"
                    ),
                )
            )

    return response


def can_manage_tags(user: User, character: EveCharacter) -> bool:
    if character.user == user:
        return True
    if user.is_superuser:
        return True
    if user_in_team(TECH_TEAM) or user_in_team(PEOPLE_TEAM):
        return True
    return False


@router.get(
    "/{int:character_id}/tags",
    summary="Get tags for a character",
    auth=AuthBearer(),
    response={
        200: List[CharacterTagResponse],
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def get_character_tags(request, character_id: int):
    character = EveCharacter.objects.filter(character_id=character_id).first()
    if not character:
        return 403, ErrorResponse.log("Character not found", character_id)
    if not can_manage_tags(request.user, character):
        return 403, ErrorResponse.log(
            "Cannot manage tags for this character", character_id
        )

    tags = EveCharacterTag.objects.filter(character=character)
    response = []
    for tag in tags:
        response.append(
            CharacterTagResponse(
                id=tag.tag_id,
                title=tag.tag.title,
                description=tag.tag.description,
                image_name=tag.tag.image_name,
            )
        )
    return response


@router.post(
    "/{int:character_id}/tags",
    summary="Add tags for a character",
    auth=AuthBearer(),
    response={
        200: None,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def add_character_tags(request, character_id: int, payload: List[int]):
    character = EveCharacter.objects.get(character_id=character_id)
    if not can_manage_tags(request.user, character):
        return 403, ErrorResponse(detail="Cannot manage tags for this user")

    for tag_id in payload:
        EveCharacterTag.objects.get_or_create(
            character=character,
            tag_id=tag_id,
        )

    return 200


@router.delete(
    "/{int:character_id}/tags/{int:tag_id}",
    summary="Remove a tag from a character",
    auth=AuthBearer(),
    response={
        200: None,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def remove_character_tag(request, character_id: int, tag_id: int):
    character = EveCharacter.objects.get(character_id=character_id)
    if not can_manage_tags(request.user, character):
        return 403, ErrorResponse(detail="Cannot manage tags for this user")

    tag = EveCharacterTag.objects.get(id=tag_id)
    tag.delete()

    return 200


@router.put(
    "/{int:character_id}/tags",
    summary="Replace a character's tags",
    auth=AuthBearer(),
    response={
        200: None,
        403: ErrorResponse,
        404: ErrorResponse,
    },
)
def replace_character_tags(request, character_id: int, payload: List[int]):
    character = EveCharacter.objects.get(character_id=character_id)
    if not can_manage_tags(request.user, character):
        return 403, ErrorResponse(detail="Cannot manage tags for this user")

    EveCharacterTag.objects.filter(character=character).delete()
    add_character_tags(request, character_id, payload)

    return 200
