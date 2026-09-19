"""Keep the feed watching every campaign system.

The activity feed only stores killmails for systems on its monitored list, so
a campaign system that is not on that list would silently produce no kills.
Adding a system to a campaign adds it to the feed.
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from campaigns.models import CampaignSystem
from feed.models import FeedMonitoredSystem

logger = logging.getLogger(__name__)


@receiver(
    post_save,
    sender=CampaignSystem,
    dispatch_uid="campaigns_monitor_system",
)
def monitor_campaign_system(sender, instance: CampaignSystem, **kwargs):
    monitored, created = FeedMonitoredSystem.objects.get_or_create(
        solar_system_id=instance.solar_system_id,
        defaults={
            "name": instance.name,
            "source": FeedMonitoredSystem.Source.MANUAL,
            "is_active": True,
        },
    )
    # A row left over from an earlier campaign may have been switched off,
    # which is exactly the silent no-kills failure this guards against.
    if not created and not monitored.is_active:
        monitored.is_active = True
        monitored.save(update_fields=["is_active"])
        logger.info("Re-enabled feed monitoring for %s", instance.name)

    if created:
        logger.info(
            "Added %s to the feed's monitored systems for campaign %s",
            instance.name,
            instance.campaign_id,
        )
