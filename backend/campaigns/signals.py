"""Keep the feed watching every campaign system.

The activity feed only stores killmails for systems on its monitored list, so
a campaign system that is not on that list would silently produce no kills.
Adding a system to a campaign adds it to the feed; retiring the last live
campaign for a system turns campaign-sourced rows back off.

Also fills a default arc when an FW objective has a goal but no arc yet, so
operators configuring from the campaign change page still get week targets.

And keeps the campaign's Discord current (``services.discord_posts``): fleet
and timer changes refresh the boards, a campaign fleet starting pings, and a
coordinator who signs in late gets their invite DM.
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from campaigns.helpers import ensure_default_arc, fill_system_name_from_feed
from campaigns.models import Campaign, CampaignStructure, CampaignSystem
from campaigns.services import coordinators, discord_posts
from campaigns.services import structures as structure_service
from eveonline.models import EveCharacter
from fleets.models import EveFleet
from structures.models import EveStructureTimer

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


# --- Campaign Discord (services.discord_posts) ---------------------------


def _refresh_boards(campaign_ids, kind: str) -> None:
    for campaign in Campaign.objects.filter(
        id__in=[cid for cid in campaign_ids if cid]
    ):
        if discord_posts.has_board(campaign, kind):
            discord_posts.queue_board_refresh(campaign.id, kind)


@receiver(pre_save, sender=EveFleet, dispatch_uid="campaigns_fleet_before")
def remember_fleet_before(sender, instance: EveFleet, **kwargs):
    old = (
        EveFleet.objects.filter(pk=instance.pk)
        .values("campaign_id", "status")
        .first()
        if instance.pk
        else None
    )
    instance.campaign_before = old or {}


@receiver(post_save, sender=EveFleet, dispatch_uid="campaigns_fleet_discord")
def campaign_fleet_discord(sender, instance: EveFleet, created, **kwargs):
    """Refresh the fleet schedules the fleet is on (or just left), and ping
    when a campaign fleet starts forming."""
    before = getattr(instance, "campaign_before", {}) or {}
    campaign_ids = {instance.campaign_id, before.get("campaign_id")}
    if not any(campaign_ids):
        return
    _refresh_boards(campaign_ids, discord_posts.SCHEDULE)
    started = instance.status == "active" and before.get("status") != "active"
    if started and instance.campaign_id:
        discord_posts.announce_fleet(instance)


@receiver(post_delete, sender=EveFleet, dispatch_uid="campaigns_fleet_deleted")
def campaign_fleet_deleted(sender, instance: EveFleet, **kwargs):
    if instance.campaign_id:
        _refresh_boards({instance.campaign_id}, discord_posts.SCHEDULE)


def _timer_campaign_ids(timer) -> set:
    ids = set(
        CampaignStructure.objects.filter(timer_id=timer.pk).values_list(
            "campaign_id", flat=True
        )
    )
    ids.add(timer.campaign_id)
    return ids


@receiver(
    post_save, sender=EveStructureTimer, dispatch_uid="campaigns_timer_board"
)
def campaign_timer_saved(sender, instance, **kwargs):
    _refresh_boards(_timer_campaign_ids(instance), discord_posts.TIMERS)


@receiver(
    post_delete,
    sender=EveStructureTimer,
    dispatch_uid="campaigns_timer_board_deleted",
)
def campaign_timer_deleted(sender, instance, **kwargs):
    # The recon row's link is cleared by now; the beat catches those.
    _refresh_boards({instance.campaign_id}, discord_posts.TIMERS)


@receiver(
    post_save, sender=EveCharacter, dispatch_uid="campaigns_coordinator_dm"
)
def notify_new_coordinator_owner(sender, instance: EveCharacter, **kwargs):
    """Someone signed in with a character invited as a coordinator before
    they were on the site: send them the invite DM now."""
    if not instance.user_id:
        return
    coordinators.notify_pending(instance)
