"""Keep the feed watching every campaign system.

The activity feed only stores killmails for systems on its monitored list, so
a campaign system that is not on that list would silently produce no kills.
Adding a system to a campaign adds it to the feed; retiring the last live
campaign for a system turns campaign-sourced rows back off.

Also fills a default arc when an FW objective has a goal but no arc yet, so
operators configuring from the campaign change page still get week targets.
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from campaigns.helpers import ensure_default_arc, fill_system_name_from_feed
from campaigns.models import CampaignSystem
from campaigns.services import structures as structure_service

logger = logging.getLogger(__name__)


@receiver(
    post_save,
    sender=CampaignSystem,
    dispatch_uid="campaigns_monitor_system",
)
def monitor_campaign_system(sender, instance: CampaignSystem, **kwargs):
    if instance.retired_at is not None:
        structure_service.deactivate_unused_campaign_monitors(
            instance.solar_system_id
        )
        return

    structure_service.ensure_feed_monitoring(
        instance.solar_system_id, instance.name
    )


@receiver(
    post_save,
    sender=CampaignSystem,
    dispatch_uid="campaigns_default_arc",
)
def default_arc_for_fw_system(sender, instance: CampaignSystem, **kwargs):
    updated_fields = []
    if fill_system_name_from_feed(instance):
        updated_fields.append("name")
    if updated_fields:
        # Avoid recursion: update_fields-only save still fires post_save, but
        # fill_system_name_from_feed is a no-op once the name is set.
        CampaignSystem.objects.filter(pk=instance.pk).update(
            name=instance.name
        )
    ensure_default_arc(instance)
