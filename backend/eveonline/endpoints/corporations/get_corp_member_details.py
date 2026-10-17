"""GET /corporations/{corporation_id}/members - corporation member details."""

from collections import defaultdict

from django.db.models import Count
from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.endpoints.corporations.schemas import (
    CorporationMemberAccess,
    CorporationMemberDetails,
)
from eveonline.helpers.corporations.permissions import (
    can_manage_corporation_projects,
    can_view_corporation_members,
    can_view_corporation_projects,
    can_view_member_characters,
    user_is_ceo,
)
from eveonline.helpers.corporations.profile import load_corporation
from eveonline.helpers.corporations.stats_cache import corporation_stats
from eveonline.models import EveCharacter, EvePlayer
from groups.models import UserCommunityStatus

router = Router(tags=["Corporations"])


@router.get(
    "corporations/{corporation_id}/members",
    response={
        200: list[CorporationMemberDetails],
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Get corporation member details (leadership only)",
)
def get_corp_member_details(request, corporation_id: int):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_view_corporation_members(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    return member_details(
        corporation_members(corporation),
        reveal_characters=can_view_member_characters(
            request.user, corporation
        ),
        stats=corporation_stats(corporation.corporation_id),
    )


@router.get(
    "corporations/{corporation_id}/members/access",
    response={200: CorporationMemberAccess, 404: ErrorResponse},
    auth=AuthBearer(),
    summary="What the current user may see of a corporation's roster",
)
def get_corp_member_access(request, corporation_id: int):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    return {
        "can_view_members": can_view_corporation_members(
            request.user, corporation
        ),
        "can_view_characters": can_view_member_characters(
            request.user, corporation
        ),
        "can_edit_settings": user_is_ceo(request.user, corporation),
        "can_view_projects": can_view_corporation_projects(
            request.user, corporation
        ),
        "can_manage_projects": can_manage_corporation_projects(
            request.user, corporation
        ),
    }


# EveCharacter rows carry large JSON columns; load only what the roster uses.
MEMBER_FIELDS = (
    "character_id",
    "character_name",
    "corporation_id",
    "user_id",
    "user__username",
    "token_id",
    "esi_suspended",
    "exempt",
    "esi_token_level",
)


def corporation_members(corporation) -> list[EveCharacter]:
    return list(
        EveCharacter.objects.filter(corporation_id=corporation.corporation_id)
        .select_related("user")
        .only(*MEMBER_FIELDS)
        .annotate(token_count=Count("token"))
    )


def member_details(
    members: list[EveCharacter],
    reveal_characters: bool = True,
    stats: dict | None = None,
) -> list[CorporationMemberDetails]:
    """Roster rows. Fleets, kills, voice and timezones come from the cached
    stats (see stats_cache); they read as zero/empty until the first refresh.
    """
    stats = stats or {}
    activity = stats.get("member_activity") or {}
    declared = stats.get("declared_by_user") or {}
    observed = stats.get("observed_by_user") or {}
    user_ids = [member.user_id for member in members if member.user_id]
    statuses = dict(
        UserCommunityStatus.objects.filter(user_id__in=user_ids).values_list(
            "user_id", "status"
        )
    )
    players_by_user = {
        player.user_id: player
        for player in EvePlayer.objects.filter(
            user_id__in=user_ids
        ).select_related("primary_character")
    }
    response = []
    for character in members:
        metrics = activity.get(character.character_id, {})
        user_id = character.user_id
        detail = CorporationMemberDetails(
            character_id=character.character_id,
            character_name=character.character_name,
            esi_suspended=character.esi_suspended,
            exempt=character.exempt,
            registered=bool(character.token_id),
            token_count=character.token_count,
            token_level=character.esi_token_level or "",
            fleets_90d=metrics.get("fleets_90d", 0),
            kills_90d=metrics.get("kills_90d", 0),
            voice_hours_90d=metrics.get("voice_hours_90d", 0),
            prime_time=declared.get(user_id) if user_id else None,
            observed_prime_times=(
                observed.get(user_id, []) if user_id else []
            ),
            community_status=statuses.get(user_id) if user_id else None,
        )
        if character.user:
            detail.user_name = character.user.username
        player = players_by_user.get(user_id) if user_id else None
        primary = player.primary_character if player else None
        if primary is not None:
            detail.primary_character_id = primary.character_id
            detail.primary_character_name = primary.character_name
        response.append(detail)
    if reveal_characters:
        return response
    return _one_row_per_person(members, response)


def _one_row_per_person(
    members: list[EveCharacter], rows: list[CorporationMemberDetails]
) -> list[CorporationMemberDetails]:
    """Collapse each linked person to one row without naming their characters.

    The row shows the person's primary (or one in-corp character when no
    primary is set) and only counts the rest, so the response never maps a
    character to its owner.
    """
    by_user = defaultdict(list)
    people = []
    for character, row in zip(members, rows):
        if character.user_id:
            by_user[character.user_id].append(row)
        else:
            people.append(row)
    for group in by_user.values():
        people.append(_person_row(group))
    return people


def _person_row(group: list[CorporationMemberDetails]):
    primary_id = group[0].primary_character_id
    identity = next(
        (row for row in group if row.character_id == primary_id), None
    )
    if identity is None and primary_id is None:
        identity = min(group, key=lambda row: row.character_name.lower())
    in_corp_identity = identity is not None
    return CorporationMemberDetails(
        character_id=identity.character_id if identity else primary_id,
        character_name=(
            identity.character_name
            if identity
            else group[0].primary_character_name
        ),
        primary_character_id=primary_id,
        primary_character_name=group[0].primary_character_name,
        registered=any(row.registered for row in group),
        exempt=identity.exempt if identity else False,
        esi_suspended=identity.esi_suspended if identity else False,
        token_count=sum(row.token_count for row in group),
        token_level=identity.token_level if identity else "",
        fleets_90d=sum(row.fleets_90d for row in group),
        kills_90d=sum(row.kills_90d for row in group),
        # Voice hours are tracked per person, so every row carries the same.
        voice_hours_90d=max(row.voice_hours_90d for row in group),
        prime_time=group[0].prime_time,
        observed_prime_times=group[0].observed_prime_times,
        community_status=group[0].community_status,
        characters_hidden=True,
        hidden_character_count=len(group) - (1 if in_corp_identity else 0),
    )
