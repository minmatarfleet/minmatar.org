from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from esi.decorators import token_required
from .models import EvePrimaryToken, EveCorporation
from pydantic import BaseModel
from typing import List

MILITIA_SCOPES = [
    "esi-characters.read_loyalty.v1",
    "esi-killmails.read_killmails.v1",
    "esi-characters.read_fw_stats.v1",
]

ALLIANCE_SCOPES = [
    "esi-wallet.read_character_wallet.v1",
    "esi-skills.read_skills.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-characters.read_loyalty.v1",
    "esi-killmails.read_killmails.v1",
    "esi-characters.read_fw_stats.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
    "esi-assets.read_assets.v1",
] + MILITIA_SCOPES

ASSOCIATE_SCOPES = [
    "esi-planets.manage_planets.v1",
    "esi-industry.read_character_jobs.v1",
    "esi-industry.read_character_mining.v1",
] + ALLIANCE_SCOPES


class CharacterResponse(BaseModel):
    character_id: int
    character_name: str
    type: str = "Public"
    scopes: List[str]
    is_primary: bool = False


class CorporationResponse(BaseModel):
    alliance_section: List[List[dict]]
    associate_section: List[List[dict]]
    militia_section: List[List[dict]]


# Create your views here.
def list_characters(request):
    characters = {}
    for token in request.user.token_set.all():
        if token.character_id not in characters:
            characters[token.character_id] = CharacterResponse(
                character_id=token.character_id,
                character_name=token.character_name,
                scopes=[scope.name for scope in token.scopes.all()],
            )
        else:
            characters[token.character_id].scopes += [
                scope.name for scope in token.scopes.all()
            ]

    # Check if a primary token exists and set the flag
    if EvePrimaryToken.objects.filter(user=request.user).exists():
        characters[
            EvePrimaryToken.objects.get(user=request.user).token.character_id
        ].is_primary = True

    # Check scopes for character_id and set type
    for character in characters.values():
        if set(character.scopes).issuperset(set(ALLIANCE_SCOPES)):
            character.type = "Alliance"
        elif set(character.scopes).issuperset(set(ASSOCIATE_SCOPES)):
            character.type = "Associate"
        elif set(character.scopes).issuperset(set(MILITIA_SCOPES)):
            character.type = "Militia"
        else:
            character.type = "Public"

    context = {
        "characters": [character for character in characters.values()],
    }

    return render(request, "eveonline/list_characters.html", context)


@login_required
@token_required()
def add_character(request, token):
    user = User.objects.get(pk=request.user.id)
    if not EvePrimaryToken.objects.filter(user=user).exists():
        EvePrimaryToken.objects.create(user=user, token=token)
    return redirect("eveonline-characters")


def list_corporations(request):
    n = 3
    alliance_corporations = EveCorporation.objects.filter(type="alliance")
    # break into n-sized chunks
    alliance_corporations = [
        alliance_corporations[i : i + n]
        for i in range(0, len(alliance_corporations), n)
    ]

    associate_corporations = EveCorporation.objects.filter(type="associate")
    # break into n-sized chunks
    associate_corporations = [
        associate_corporations[i : i + n]
        for i in range(0, len(associate_corporations), n)
    ]

    militia_corporations = EveCorporation.objects.filter(type="militia")
    # break into n-sized chunks
    militia_corporations = [
        militia_corporations[i : i + n]
        for i in range(0, len(militia_corporations), n)
    ]

    context = {
        "alliance_corporation_chunks": alliance_corporations,
        "associate_corporation_chunks": associate_corporations,
        "militia_corporation_chunks": militia_corporations,
    }

    return render(request, "eveonline/list_corporations.html", context)
