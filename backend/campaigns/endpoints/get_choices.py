"""One endpoint: see the function below."""

from __future__ import annotations

from authentication import AuthBearer

from campaigns.endpoints import schemas
from campaigns.endpoints.base import router
from campaigns.models import (
    CampaignKind,
    CampaignStatus,
    CampaignWeekTarget,
    PartyKind,
    PartySide,
    SiteKind,
    SystemGoal,
    SystemPriority,
    SystemRole,
)


def _choices(choices) -> list[dict]:
    return [
        {"value": value, "label": label} for value, label in choices.choices
    ]


@router.get(
    "/choices",
    response={200: schemas.CampaignChoicesOut},
    auth=AuthBearer(),
)
def list_choices(request):
    """The labels of every stored choice, so forms never show raw values."""
    return {
        "status": _choices(CampaignStatus),
        "kind": _choices(CampaignKind),
        "goal": _choices(SystemGoal),
        "role": _choices(SystemRole),
        "priority": _choices(SystemPriority),
        "party_kind": _choices(PartyKind),
        "party_side": _choices(PartySide),
        "site_kind": _choices(SiteKind),
        "metric": _choices(CampaignWeekTarget.Metric),
    }
