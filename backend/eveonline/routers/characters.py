import json
import logging
import datetime
from typing import List, Optional

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from esi.decorators import token_required
from esi.models import Token
from ninja import Router
from pydantic import BaseModel

from authentication import AuthBearer
from eveonline.models import (
    EveCharacter,
    EveCharacterAsset,
    EveCharacterLog,
    EveCharacterSkillset,
    EvePrimaryCharacter,
    EvePrimaryCharacterChangeLog,
)
from eveonline.scopes import (
    TokenType,
    scopes_for,
    scope_group,
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


class ErrorResponse(BaseModel):
    detail: str


class UserCharacter(BaseModel):
    character_id: int
    character_name: str
    is_primary: bool


class UserCharacterResponse(BaseModel):
    user_id: int
    user_name: str
    discord_id: str
    characters: List[UserCharacter]


class CharacterTokenInfo(BaseModel):
    id: str
    created: datetime.datetime
    expires: datetime.datetime
    can_refresh: bool
    owner_hash: str
    scopes: List[str]
    level: str


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
            return 404, {"detail": "Primary character not found."}
        character = EveCharacter.objects.get(character_id=primary_character_id)
        character_user = character.token.user
        characters = EveCharacter.objects.filter(token__user=character_user)
    else:
        characters = EveCharacter.objects.filter(token__user=request.user)
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
    "/{int:character_id}",
    summary="Get character by ID",
    auth=AuthBearer(),
    response={200: CharacterResponse, 403: ErrorResponse, 404: ErrorResponse},
)
def get_character_by_id(request, character_id: int):
    if not EveCharacter.objects.filter(character_id=character_id).exists():
        return 404, {"detail": "Character not found."}

    character = EveCharacter.objects.get(character_id=character_id)

    payload = {
        "character_id": character.character_id,
        "character_name": character.character_name,
    }

    if character.token:
        primary_character = EvePrimaryCharacter.objects.filter(
            character__token__user=character.token.user
        ).first()
        if (
            primary_character
            and primary_character.character.character_id != character_id
        ):
            payload["primary_character_id"] = (
                primary_character.character.character_id
            )
            payload["primary_character_name"] = (
                primary_character.character.character_name
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
    if EvePrimaryCharacter.objects.filter(
        character__token__user=request.user
    ).exists():
        primary_character = fetch_primary_character(request.user)
        if primary_character.character.character_id == character_id:
            characters = EveCharacter.objects.filter(
                token__user=request.user
            ).exclude(character_id=character_id)
            if characters.exists():
                primary_character.character = characters.first()
                primary_character.save()
    try:
        EveCharacter.objects.filter(character_id=character_id).delete()
        Token.objects.filter(character_id=character_id).delete()
    except Exception as e:
        return 500, str(e)

    return 200, None


@router.put(
    "/primary",
    summary="Set primary character",
    auth=AuthBearer(),
    response={200: None, 404: ErrorResponse},
)
def set_primary_character(request, character_id: int):
    if not EveCharacter.objects.filter(character_id=character_id).exists():
        return 404, {"detail": "Character not found."}

    character = EveCharacter.objects.get(character_id=character_id)
    if not request.user.is_superuser:
        if not character.token.user == request.user:
            return 403, {
                "detail": "You do not have permission to set this character as primary."
            }

    primary_characters = EvePrimaryCharacter.objects.filter(
        character__token__user=request.user
    ).distinct()
    if primary_characters.exists():
        # Delete any existing primary character records, after creating change log
        if primary_characters.count() > 1:
            logger.error(
                "User %s has %d primary characters",
                request.user.username,
                primary_characters.count,
            )
        for primary_character in primary_characters.all():
            EvePrimaryCharacterChangeLog.objects.create(
                username=request.user.username,
                previous_character_name=primary_character.character.character_name,
                new_character_name=character.character_name,
            )
            primary_character.delete()

    EvePrimaryCharacter.objects.create(character=character)
    return 200, None


def fetch_primary_character(user) -> EveCharacter | None:
    q = EvePrimaryCharacter.objects.filter(character__token__user=user)

    if q.count() > 1:
        logger.error(
            "User %s has %d primary characters", user.username, q.count()
        )

    if q.count() >= 1:
        return q.first().character
    else:
        return None


@router.get(
    "/primary",
    summary="Get primary character",
    auth=AuthBearer(),
    response={200: BasicCharacterResponse, 404: ErrorResponse},
)
def get_primary_character(request):
    character = fetch_primary_character(request.user)

    if character is None:
        return 404, {"detail": "Primary character not found."}

    return {
        "character_id": character.character_id,
        "character_name": character.character_name,
    }


@router.get("/add", summary="Add character using EVE Online SSO")
def add_character(request, redirect_url: str, token_type: TokenType):
    request.session["redirect_url"] = redirect_url
    scopes = scopes_for(token_type)

    @login_required()
    @token_required(scopes=scopes, new=True)
    def wrapped(request, token):
        if EveCharacter.objects.filter(
            character_id=token.character_id
        ).exists():
            logger.info(
                "Character %s already exists, updating token",
                token.character_id,
            )
            character = EveCharacter.objects.get(
                character_id=token.character_id
            )
            if (
                character.token
                and character.token != token
                and len(token.scopes.all()) > len(character.token.scopes.all())
            ):
                logger.info(
                    "New token has more scopes, deleting old character token"
                )
                old_token = character.token
                character.token = token
                character.esi_token_level = token_type.value
                character.save()
                old_token.delete()
            elif not character.token:
                logger.info(
                    "Character %s has no token, adding token",
                    token.character_id,
                )
                character.token = token
                character.esi_token_level = token_type.value
                character.save()
            elif token != character.token:
                logger.info(
                    "Character %s already has better token, throwing this one away",
                    token.character_id,
                )
                token.delete()

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
        else:
            logger.info(
                "Creating new character %s with token",
                token.character_id,
            )
            character = EveCharacter.objects.create(
                character_id=token.character_id,
                character_name=token.character_name,
                esi_token_level=token_type,
                token=token,
            )
        EveCharacterLog.objects.create(
            username=request.user.username,
            character_name=character.character_name,
        )
        # set as primary character if only one character
        if (
            not EvePrimaryCharacter.objects.filter(
                character__token__user=request.user
            ).exists()
            and EveCharacter.objects.filter(token__user=request.user).count()
            == 1
        ):
            logger.info(
                "Setting %s as primary character for user %s",
                character.character_name,
                request.user.username,
            )
            EvePrimaryCharacter.objects.create(character=character)

        # populate corporation if CEO token
        if token_type in [TokenType.CEO, TokenType.MARKET, TokenType.FREIGHT]:
            logger.info(
                "Populating CEO token corporation for character %s",
                character.character_id,
            )
            character.corporation.populate()

        return redirect(request.session["redirect_url"])

    return wrapped(request)  # pylint: disable=no-value-for-parameter


def fixup_character_token_level(character, token_count):
    if not character.esi_token_level:
        if token_count == 1 and not character.token:
            character.token = Token.objects.filter(
                character_id=character.character_id
            ).first()
        if character.token:
            character.esi_token_level = scope_group(character.token)
            character.save()


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
    if not request.user.is_superuser:
        return 403, ErrorResponse(detail="Not authorised")

    if discord_id and character_name:
        return 400, ErrorResponse(
            detail="Only one query parameter can be provided"
        )

    if character_name:
        char = EveCharacter.objects.filter(
            character_name=character_name
        ).first()

        if not char:
            return 404, ErrorResponse(detail="No matching character found")

        if not char.token:
            return 400, ErrorResponse(detail="Character not linked to a user")

        char_user = char.token.user

        discord_user = DiscordUser.objects.filter(user=char_user).first()
    elif discord_id:
        discord_user = DiscordUser.objects.filter(id=discord_id).first()

        if not discord_user:
            return 404, ErrorResponse(detail="No matching discord user found")

        char_user = discord_user.user
    else:
        return 400, ErrorResponse(
            detail="A character name or discord ID must be specified"
        )

    response = UserCharacterResponse(
        user_id=char_user.id,
        user_name=char_user.username,
        discord_id=str(discord_user.id),
        characters=[],
    )

    primary = EvePrimaryCharacter.objects.filter(
        character__token__user=char_user
    ).first()

    chars = EveCharacter.objects.filter(token__user=char_user)
    for char in chars.all():
        response.characters.append(
            UserCharacter(
                character_id=char.character_id,
                character_name=char.character_name,
                is_primary=(primary and char == primary.character),
            )
        )

    return response


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

    for token in character.tokens:
        if is_admin or token.user is request.user:
            scopes = []
            for scope in token.scopes.all():
                scopes.append(scope.name)

            response.append(
                CharacterTokenInfo(
                    id=str(token.pk),
                    created=token.created,
                    expires=token.expires,
                    can_refresh=token.can_refresh,
                    owner_hash=token.character_owner_hash,
                    scopes=scopes,
                    level=scope_group(token),
                )
            )

    return response
