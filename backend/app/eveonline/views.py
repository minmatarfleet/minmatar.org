from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from esi.decorators import token_required
from eveonline.helpers.skills import compare_skills_to_skillset
from .models import (
    EvePrimaryToken,
    EveCorporation,
    EveCorporationApplication,
    EveCharacter,
    EveCharacterSkillset,
)
from .forms import EveCorporationApplicationForm
from pydantic import BaseModel
from typing import List
from django.contrib import messages
from eveonline.helpers.characters import (
    get_character_list,
    get_corporation_character_list,
    ALLIANCE_SCOPES,
    TokenType,
)
from datetime import timedelta
from django.utils import timezone


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
@login_required
def list_characters(request):
    characters = get_character_list(request.user)
    context = {
        "characters": characters,
    }

    return render(
        request, "eveonline/characters/list_characters.html", context
    )


@login_required
@permission_required("eveonline.view_evecharacter")
def view_character(request, character_id):
    character = EveCharacter.objects.get(character_id=character_id)
    skillsets = EveCharacterSkillset.objects.all()

    skillsets_response = []
    for skillset in skillsets:
        missing_skills, progress = compare_skills_to_skillset(
            character, skillset
        )
        progress_color = "success"
        if progress < 50:
            progress_color = "danger"
        elif progress < 100:
            progress_color = "warning"
        skillsets_response.append(
            {
                "skillset": skillset,
                "missing_skills": "\n".join(missing_skills),
                "progress": {"value": progress, "color": progress_color},
            }
        )

    context = {
        "character": character,
        "skillsets": skillsets_response,
    }

    return render(request, "eveonline/characters/view_character.html", context)


@login_required
@token_required()
def add_character(request, token):
    user = User.objects.get(pk=request.user.id)
    if not EvePrimaryToken.objects.filter(user=user).exists():
        EvePrimaryToken.objects.create(user=user, token=token)
    return redirect("eveonline-characters")


@login_required
@token_required(scopes=ALLIANCE_SCOPES)
def add_alliance_character(request, token):
    next = request.GET.get("next", None)
    user = User.objects.get(pk=request.user.id)
    if not EvePrimaryToken.objects.filter(user=user).exists():
        EvePrimaryToken.objects.create(user=user, token=token)
    if next:
        return redirect(next)
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

    return render(
        request, "eveonline/corporations/list_corporations.html", context
    )


def view_corporation(request, corporation_pk):
    corporation = EveCorporation.objects.get(pk=corporation_pk)
    characters = get_corporation_character_list(corporation)
    context = {
        "corporation": corporation,
        "characters": characters,
    }
    return render(
        request, "eveonline/corporations/view_corporation.html", context
    )


@login_required
@token_required(scopes=EveCorporation.required_ceo_scopes)
def update_corporation(request, token, corporation_pk):
    corporation = EveCorporation.objects.get(pk=corporation_pk)
    if token.character_id == corporation.ceo_id:
        messages.success(
            request, "Successfully added CEO token for corporation"
        )
    else:
        messages.error(request, "Must be the CEO to add token for corporation")
    return redirect("eveonline-corporations")


@login_required
def create_corporation_application(request, corporation_pk):
    corporation = EveCorporation.objects.get(pk=corporation_pk)
    characters = get_character_list(request.user)
    if EveCorporationApplication.objects.filter(
        corporation=corporation,
        user=request.user,
        created_at__gt=timezone.now() - timedelta(days=30),
    ).exists():
        existing_application = EveCorporationApplication.objects.get(
            corporation=corporation,
            user=request.user,
        )
    else:
        existing_application = None
    for character in characters:
        if character.type != TokenType.ALLIANCE:
            messages.warning(
                request,
                f"Token for {character.character_name} has an improper token type. Please add this character again",
            )
    if request.method == "POST":
        submit = True
        form = EveCorporationApplicationForm(request.POST)
        # Check characters
        if not characters:
            messages.error(
                request,
                "You must have at least one character to apply to a corporation",
            )
            submit = False

        for character in characters:
            if character.type != TokenType.ALLIANCE:
                submit = False

        # Check form
        if not form.is_valid():
            submit = False

        if submit:
            application = form.save(commit=False)
            application.corporation = EveCorporation.objects.get(
                pk=corporation_pk
            )
            application.user = request.user
            application.save()
            messages.info(request, "Successfully applied to corporation")
            return redirect("eveonline-corporations-apply", corporation_pk)
    else:
        form = EveCorporationApplicationForm()

    context = {
        "form": form,
        "characters": characters,
        "corporation": corporation,
        "existing_application": existing_application,
    }
    return render(
        request,
        "eveonline/applications/create_corporation_application.html",
        context,
    )


@login_required
@permission_required("eveonline.view_evecorporationapplication")
def view_corporation_application(request, application_pk):
    application = EveCorporationApplication.objects.get(pk=application_pk)
    discord_user = request.user.discord_user
    characters = get_character_list(application.user)
    context = {
        "application": application,
        "discord_user": discord_user,
        "characters": characters,
        "discord_thread_link": f"https://discord.com/channels/1041384161505722368/{application.discord_thread_id}",
    }
    return render(
        request,
        "eveonline/applications/view_corporation_application.html",
        context,
    )


@login_required
@permission_required("eveonline.view_evecorporationapplication")
def approve_corporation_application(request, application_pk):
    application = EveCorporationApplication.objects.get(pk=application_pk)
    application.status = "accepted"
    application.save()
    return redirect("eveonline-corporations-applications-view", application_pk)


@login_required
@permission_required("eveonline.view_evecorporationapplication")
def reject_corporation_application(request, application_pk):
    application = EveCorporationApplication.objects.get(pk=application_pk)
    application.status = "rejected"
    application.save()
    return redirect("eveonline-corporations-applications-view", application_pk)
