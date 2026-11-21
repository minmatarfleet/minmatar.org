"""Shared by the coordinator, doctrine and fitting endpoints."""

from __future__ import annotations

from django.shortcuts import get_object_or_404

from campaigns.endpoints import serializers
from campaigns.endpoints.manage import _can_manage, _denied
from campaigns.models import Campaign


def _managed(request, slug: str):
    campaign = get_object_or_404(Campaign, slug=slug)
    if not _can_manage(request.user, campaign):
        return None, _denied()
    return campaign, None


def _doctrines_out(campaign: Campaign) -> dict:
    return {
        "doctrines": [
            {
                "id": row.id,
                "doctrine_id": row.doctrine_id,
                "name": row.doctrine.name,
            }
            for row in campaign.doctrines.select_related("doctrine")
        ],
        "fittings": serializers.campaign_fittings(campaign, everything=True),
    }
