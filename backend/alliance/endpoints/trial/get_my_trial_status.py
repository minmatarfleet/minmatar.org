"""GET /api/alliance/trial/me/status - whether to show the Trial tab."""

from ninja import Router

from alliance.endpoints.trial.schemas import TrialStatusResponse
from alliance.helpers.trial_report import is_on_trial
from authentication import AuthBearer

router = Router(tags=["Alliance"])


@router.get(
    "me/status",
    response={200: TrialStatusResponse},
    auth=AuthBearer(),
    summary="Whether the current user is on trial (shows the Trial tab)",
)
def get_my_trial_status(request):
    return TrialStatusResponse(on_trial=is_on_trial(request.user))
