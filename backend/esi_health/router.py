"""/api/esi-health: Manage › ESI health, and a corporation's director token.

Everything but the director token is for superusers (the unwired
``esi_health.manage`` feature). The director token is for the corporation's
leadership, the people who see its Members tab.
"""

from typing import List

from ninja import Router

from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.helpers.corporations.permissions import (
    can_view_corporation_members,
)
from eveonline.helpers.corporations.profile import load_corporation
from eveonline.helpers.characters.identity import owned_by_q
from eveonline.models import EveCharacter
from eveonline.scopes import TokenType
from esi_health import services
from esi_health.models import ScopeRollout
from esi_health.schemas import (
    CorporationHealthResponse,
    DirectorHolderResponse,
    DirectorTokenResponse,
    MessageRequest,
    MessageResponse,
    PilotHealthResponse,
    ScopeRolloutPatch,
    ScopeRolloutResponse,
)
from groups.helpers.feature_access import can_use_feature

router = Router(tags=["ESI health"])

FEATURE = "esi_health.manage"
NOT_ALLOWED = "Only superusers manage ESI health."


def _allowed(request) -> bool:
    return can_use_feature(request.user, FEATURE)


@router.get(
    "/corporations",
    response={200: List[CorporationHealthResponse], 403: ErrorResponse},
    auth=AuthBearer(),
    summary="Every alliance corporation's ESI problems",
)
def get_corporations(request):
    if not _allowed(request):
        return 403, ErrorResponse(detail=NOT_ALLOWED)
    return 200, [
        CorporationHealthResponse(
            corporation_id=c.corporation_id,
            name=c.name,
            ticker=c.ticker,
            members=c.members,
            needs_readd=c.needs_readd,
            pilots_active=c.pilots_active,
            pilots_on_leave=c.pilots_on_leave,
            active_user_ids=c.active_user_ids,
            unlinked=c.unlinked,
            director_state=c.director.state,
            director_complete=sum(
                1 for holder in c.director.holders if holder.missing == 0
            ),
            director_holders=len(c.director.holders),
            last_messaged=c.last_messaged,
        )
        for c in services.corporations_report()
    ]


@router.get(
    "/pilots",
    response={200: List[PilotHealthResponse], 403: ErrorResponse},
    auth=AuthBearer(),
    summary="Pilots with characters to re-add",
)
def get_pilots(request):
    if not _allowed(request):
        return 403, ErrorResponse(detail=NOT_ALLOWED)
    return 200, [
        PilotHealthResponse(
            user_id=p.user_id,
            username=p.username,
            main_character_id=p.main_character_id,
            main_character_name=p.main_character_name,
            corporation_ticker=p.corporation_ticker,
            characters=p.characters,
            main_needs_readd=p.main_needs_readd,
            scope_groups=p.scope_groups,
            community_status=p.status,
            on_leave=p.on_leave,
            discord_linked=p.discord_linked,
            task_opened_at=p.task_opened_at,
            last_messaged=p.last_messaged,
            next_message_at=(
                p.last_messaged + services.MESSAGE_COOLDOWN
                if p.last_messaged
                else None
            ),
        )
        for p in services.pilots_report()
    ]


def _scope_rows() -> list[ScopeRolloutResponse]:
    return [
        ScopeRolloutResponse(
            id=row.rollout.pk,
            scope=row.rollout.scope,
            scope_group=row.rollout.scope_group,
            label=row.rollout.label,
            added_on=row.rollout.added_on,
            mode=row.rollout.mode,
            updated=row.updated,
            total=row.total,
            unit=row.unit,
        )
        for row in services.scopes_report()
    ]


@router.get(
    "/scopes",
    response={200: List[ScopeRolloutResponse], 403: ErrorResponse},
    auth=AuthBearer(),
    summary="Scopes added to a group, and how hard we ask for them",
)
def get_scopes(request):
    if not _allowed(request):
        return 403, ErrorResponse(detail=NOT_ALLOWED)
    return 200, _scope_rows()


@router.patch(
    "/scopes/{rollout_id}",
    response={
        200: ScopeRolloutResponse,
        400: ErrorResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Change how hard we ask for a scope change",
)
def patch_scope(request, rollout_id: int, payload: ScopeRolloutPatch):
    if not _allowed(request):
        return 403, ErrorResponse(detail=NOT_ALLOWED)
    rollout = ScopeRollout.objects.filter(pk=rollout_id).first()
    if rollout is None:
        return 404, ErrorResponse(detail="No such scope change.")
    director = rollout.scope_group == TokenType.DIRECTOR.value
    allowed = (
        (ScopeRollout.MODE_NONE, ScopeRollout.MODE_REQUIRE)
        if director
        else (ScopeRollout.MODE_NONE, ScopeRollout.MODE_SUGGEST)
    )
    if payload.mode not in allowed:
        return 400, ErrorResponse(
            detail=(
                "A Director scope is required or not."
                if director
                else "A character scope can only be suggested."
            )
        )
    rollout.mode = payload.mode
    rollout.updated_by = request.user
    rollout.save()
    # pylint: disable=import-outside-toplevel
    from taskboard.tasks import sync_task_rule

    for rule in ("update_scopes", "corp_director_token"):
        sync_task_rule.delay(rule)
    return 200, next(row for row in _scope_rows() if row.id == rollout_id)


@router.post(
    "/messages",
    response={200: MessageResponse, 403: ErrorResponse},
    auth=AuthBearer(),
    summary="Message pilots on Discord to re-add their characters",
)
def post_messages(request, payload: MessageRequest):
    if not _allowed(request):
        return 403, ErrorResponse(detail=NOT_ALLOWED)
    user_ids = payload.user_ids or [
        pilot.user_id for pilot in services.pilots_report()
    ]
    result = services.send_messages(request.user, user_ids)
    return 200, MessageResponse(
        sent=len(result.sent),
        on_leave=len(result.on_leave),
        recently_messaged=len(result.recently_messaged),
        nothing_to_fix=len(result.nothing_to_fix),
        no_discord=len(result.no_discord),
    )


@router.get(
    "/corporations/{corporation_id}/director-token",
    response={
        200: DirectorTokenResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Whether a corporation's director token reads everything",
)
def get_director_token(request, corporation_id: int):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_view_corporation_members(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    status = services.director_statuses([corporation_id])[corporation_id]
    mine = set(
        EveCharacter.objects.filter(owned_by_q(request.user.id)).values_list(
            "character_id", flat=True
        )
    )
    labels = dict(ScopeRollout.objects.values_list("scope", "label"))
    return 200, DirectorTokenResponse(
        state=status.state,
        holders=[
            DirectorHolderResponse(
                character_id=holder.character_id,
                character_name=holder.character_name,
                missing=holder.missing,
                is_you=holder.character_id in mine,
            )
            for holder in status.holders
        ],
        missing_scopes=status.missing_scopes,
        missing_labels=sorted(
            {labels[s] for s in status.missing_scopes if s in labels}
        ),
    )
