"""One endpoint: see the function below."""

from __future__ import annotations


from django.shortcuts import get_object_or_404
from django.utils import timezone

from app.errors import ErrorResponse
from authentication import AuthBearer

from campaigns.endpoints.base import router
from campaigns.endpoints.manage import _can_manage, _denied
from campaigns.models import (
    Campaign,
)
from campaigns.services import plan


@router.post(
    "/{slug}/commander-order/draft",
    response={200: dict, 403: ErrorResponse},
    auth=AuthBearer(),
)
def draft_commander_order(request, slug: str):
    """Write the order from the week plan and keep it as a draft."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    campaign.commander_order_text = plan.draft_commander_order(campaign)
    campaign.commander_order_set_at = timezone.now()
    campaign.commander_order_is_draft = True
    campaign.save(
        update_fields=[
            "commander_order_text",
            "commander_order_set_at",
            "commander_order_is_draft",
        ]
    )
    return {
        "commander_order_text": campaign.commander_order_text,
        "commander_order_is_draft": True,
    }
