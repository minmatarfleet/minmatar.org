"""What the campaign settings endpoints read and share."""

from __future__ import annotations

from django.utils import timezone

from campaigns.endpoints import serializers
from campaigns.helpers import campaign_week_start
from campaigns.models import (
    Campaign,
    CampaignDailyOrder,
    CampaignSystem,
    CampaignWeekTarget,
)
from eveonline.models import EveCharacter


def _system_out(system: CampaignSystem) -> dict:
    return {
        "id": system.id,
        "solar_system_id": system.solar_system_id,
        "name": system.name,
        "goal": system.goal,
        "role": system.role,
        "priority": system.priority,
        "is_fw_objective": system.is_fw_objective,
        "retired": system.retired_at is not None,
    }


def coordinators_out(campaign: Campaign) -> list[dict]:
    """Invited coordinators, whether their character is on the site, and
    the servers they forward to."""
    rows = list(campaign.coordinators.all())
    owners = dict(
        EveCharacter.objects.filter(
            character_id__in=[row.character_id for row in rows],
            user__isnull=False,
        ).values_list("character_id", "user_id")
    )
    servers: dict[int, list[str]] = {}
    for link in campaign.discord_links.all():
        servers.setdefault(link.linked_by_id, []).append(
            link.guild_name or str(link.guild_id)
        )
    return [
        {
            "id": row.id,
            "character_id": row.character_id,
            "character_name": row.character_name,
            "corporation_name": row.corporation_name,
            "alliance_name": row.alliance_name,
            "signed_in": row.character_id in owners,
            "discord_servers": servers.get(owners.get(row.character_id), []),
        }
        for row in rows
    ]


def _settings(campaign: Campaign) -> dict:
    week_start = campaign_week_start()
    return {
        "slug": campaign.slug,
        "name": campaign.name,
        "tagline": campaign.tagline,
        "description_md": campaign.description_md,
        "status": campaign.status,
        "kind": campaign.kind,
        "features": campaign.features,
        "start_at": campaign.start_at,
        "end_at": campaign.end_at,
        "commander_order_text": campaign.commander_order_text,
        "commander_order_is_draft": campaign.commander_order_is_draft,
        "systems": [_system_out(s) for s in campaign.systems.all()],
        "areas": [serializers.area_out(a) for a in campaign.areas.all()],
        "parties": [serializers.party_out(p) for p in campaign.parties.all()],
        "structures": [
            {
                "id": structure.id,
                "name": structure.name,
                "structure_type": structure.structure_type,
                "system_name": structure.system_name,
            }
            for structure in campaign.structures.all()
        ],
        "fittings": serializers.campaign_fittings(campaign, everything=True),
        "undisclosed": campaign.undisclosed,
        "public_key": campaign.public_key,
        "coordinator_scopes": list(campaign.coordinator_scopes or []),
        "coordinators": coordinators_out(campaign),
        "doctrines": [
            {
                "id": row.id,
                "doctrine_id": row.doctrine_id,
                "name": row.doctrine.name,
            }
            for row in campaign.doctrines.select_related("doctrine")
        ],
        "week_targets": [
            {
                "id": row.id,
                "system": row.campaign_system.name,
                "metric": row.metric,
                "target": row.target,
                "progress": row.progress,
                "proposed": row.proposed,
            }
            for row in CampaignWeekTarget.objects.filter(
                campaign_system__campaign=campaign, week_start=week_start
            ).select_related("campaign_system")
        ],
        "daily_orders": [
            {
                "id": order.id,
                "kind": order.kind,
                "points": order.points,
                "system": (
                    order.campaign_system.name if order.campaign_system else ""
                ),
            }
            for order in CampaignDailyOrder.objects.filter(
                campaign=campaign, day=timezone.localdate()
            ).select_related("campaign_system")
        ],
    }
