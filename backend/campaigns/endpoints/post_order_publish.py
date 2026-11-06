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


@router.post(
    "/{slug}/commander-order/publish",
    response={200: dict, 400: ErrorResponse, 403: ErrorResponse},
    auth=AuthBearer(),
)
def publish_commander_order(request, slug: str):
    """Clear the draft flag so pilots see the order."""
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return _denied()
    if not campaign.commander_order_text.strip():
        return 400, {"detail": "the order is empty"}
    campaign.commander_order_is_draft = False
    campaign.commander_order_set_at = timezone.now()
    campaign.save(
        update_fields=["commander_order_is_draft", "commander_order_set_at"]
    )
    return {
        "commander_order_text": campaign.commander_order_text,
        "commander_order_is_draft": False,
    }
