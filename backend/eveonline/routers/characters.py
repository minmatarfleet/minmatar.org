import json
from enum import Enum
from typing import List

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from esi.decorators import token_required
from esi.models import Token
from ninja import Router
from pydantic import BaseModel

from authentication import AuthBearer
from eveonline.models import EveCharacter, EveCharacterTag
from eveonline.scopes import ADVANCED_SCOPES, BASIC_SCOPES, CEO_SCOPES

router = Router(tags=["Characters"])


class TokenType(Enum):
    CEO = "CEO"
    BASIC = "Basic"
    ADVANCED = "Advanced"


class BasicCharacterResponse(BaseModel):
    character_id: int
    character_name: str
    tags: List[str]


class CharacterResponse(BasicCharacterResponse):
    skills: dict


class TagRequest(BaseModel):
    character_id: int
    tags: List[str]

@router.get(
    "/{int:character_id}",
    summary="Get character by ID",
    auth=AuthBearer(),
    response=CharacterResponse,
)
def get_character_by_id(request, character_id: int):
    character = EveCharacter.objects.get(character_id=character_id)

    if (
        request.user.has_perm("eveonline.view_evecharacter")
        or Token.objects.filter(
            user=request.user, character_id=character_id
        ).exists()
    ):
        return {
            "character_id": character.character_id,
            "character_name": character.character_name,
            "skills": json.loads(character.skills_json),
        }

    return 403, "You do not have permission to view this character."


@router.get("/add", summary="Login with EVE Online")
def add_character(request, redirect_url: str, token_type: TokenType):
    print("hi")
    request.session["redirect_url"] = redirect_url
    scopes = None
    match token_type:
        case TokenType.BASIC:
            scopes = BASIC_SCOPES
        case TokenType.ADVANCED:
            scopes = ADVANCED_SCOPES
        case TokenType.CEO:
            scopes = CEO_SCOPES

    @login_required()
    @token_required(scopes=scopes, new=True)
    def wrapped(request, _):
        return redirect(request.session["redirect_url"])

    return wrapped(request)  # pylint: disable=no-value-for-parameter


@router.get(
    "",
    summary="Get characters",
    auth=AuthBearer(),
    response=List[BasicCharacterResponse],
)
def get_characters(request):
    tokens = Token.objects.filter(user=request.user)
    response = []
    for token in tokens:
        tags = EveCharacterTag.objects.filter(character__pk=token.character_id)
        response.append(
            {
                "character_id": token.character_id,
                "character_name": token.character_name,
                "tags": list(tags)
            }
        )
    return response


@router.post(
    "/{int:character_id}/tags",
    summary="Get character tags by ID",
    auth=AuthBearer(),
    response=None,
)
def post_character_tags(request, character_id: int, tag_req: TagRequest):
    character = EveCharacter.objects.get(character_id=character_id)
    if (
        request.user.has_perm("eveonline.change_evecharacter")
        or Token.objects.filter(
            user=request.user, character_id=character_id
        ).exists()
    ):
        for tag in tag_req.tags:
            EveCharacterTag.objects.create(character=character, tag=tag)
        return 204
    return 403, "You do not have permission to view this character."
