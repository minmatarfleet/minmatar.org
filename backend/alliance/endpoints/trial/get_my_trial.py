"""GET /api/alliance/trial/me - the signed-in pilot's Trial tab."""

from ninja import Router

from alliance.endpoints.trial.schemas import TrialReportResponse
from alliance.helpers.trial_report import is_on_trial, pilot_report
from authentication import AuthBearer
from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCorporation

router = Router(tags=["Alliance"])


@router.get(
    "me",
    response={200: TrialReportResponse},
    auth=AuthBearer(),
    summary="The current user's trial: length, tiers and ships brought",
)
def get_my_trial(request):
    if not is_on_trial(request.user):
        return TrialReportResponse(on_trial=False)
    primary = user_primary_character(request.user)
    corporation_id = primary.corporation_id if primary else None
    ticker = (
        EveCorporation.objects.filter(corporation_id=corporation_id)
        .values_list("ticker", flat=True)
        .first()
        if corporation_id
        else None
    )
    return TrialReportResponse(
        on_trial=True,
        corporation_ticker=ticker,
        **pilot_report(request.user, corporation_id),
    )
