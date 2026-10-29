"""GET /corporations/{corporation_id}/members/{character_id}/insights

The expanded Members row: how the person compares with active pilots, their
trial progress, the ships they bring to fleets and their kills. Loaded when
the row opens, so the roster itself stays one cached read.
"""

from ninja import Router

from alliance.endpoints.trial.schemas import MemberInsightsResponse
from alliance.helpers.trial_report import member_insights
from app.errors import ErrorResponse
from authentication import AuthBearer
from eveonline.helpers.corporations.permissions import (
    can_promote_corporation_trials,
    can_view_corporation_members,
)
from eveonline.helpers.corporations.profile import load_corporation
from eveonline.models import EveCharacter
from groups.models import UserCommunityStatus

router = Router(tags=["Corporations"])


@router.get(
    "corporations/{corporation_id}/members/{character_id}/insights",
    response={
        200: MemberInsightsResponse,
        403: ErrorResponse,
        404: ErrorResponse,
    },
    auth=AuthBearer(),
    summary="Trial, tiers, ships and kills for one member (leadership only)",
)
def get_corp_member_insights(request, corporation_id: int, character_id: int):
    corporation = load_corporation(corporation_id)
    if corporation is None:
        return 404, ErrorResponse(detail="Corporation not found")
    if not can_view_corporation_members(request.user, corporation):
        return 403, ErrorResponse(detail="Not authorised")
    character = (
        EveCharacter.objects.filter(character_id=character_id)
        .select_related("user")
        .first()
    )
    if character is None or not in_corporation(character, corporation_id):
        return 404, ErrorResponse(detail="Member not found")
    insights = member_insights(character, corporation_id)
    # The trial bar comes from the daily snapshot; the status is live, so a
    # member promoted today stops showing a trial straight away.
    status = (
        UserCommunityStatus.objects.filter(user_id=character.user_id)
        .values_list("status", flat=True)
        .first()
        if character.user_id
        else None
    )
    on_trial = status == UserCommunityStatus.STATUS_TRIAL
    if not on_trial:
        insights["trial"] = None
    return MemberInsightsResponse(
        corporation_ticker=corporation.ticker,
        on_trial=on_trial,
        can_promote=on_trial
        and can_promote_corporation_trials(request.user, corporation),
        **insights,
    )


def in_corporation(character: EveCharacter, corporation_id: int) -> bool:
    """The character, or another character of the same person, is in the
    corp (a roster row can show a main that sits in another corp)."""
    if character.corporation_id == corporation_id:
        return True
    if not character.user_id:
        return False
    return EveCharacter.objects.filter(
        user_id=character.user_id, corporation_id=corporation_id
    ).exists()
