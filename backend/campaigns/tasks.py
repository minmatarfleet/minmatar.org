"""Scheduled work for campaigns.

Nothing here is the only path to a fact. The stream attributes kills as they
land, the sweep re-attributes the last two days, the payout poll finds site
completions and the cross-check confirms we did not miss a kill.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

from app.celery import app
from campaigns.helpers import campaign_day
from campaigns.models import (
    Campaign,
    CampaignEnlistmentCharacter,
    CampaignEvent,
    CampaignKillmail,
    CampaignStatus,
)
from campaigns.services import (
    attribution,
    esi_gate,
    names,
    plan,
    sites,
    snapshots,
    stats,
)
from eveonline.client import EsiClient
from eveonline.models import EveCharacterFwLpPayout

logger = logging.getLogger(__name__)


def _live_campaigns():
    return Campaign.objects.filter(
        status__in=[CampaignStatus.SCHEDULED, CampaignStatus.ACTIVE]
    )


@app.task()
def sweep_campaign_killmails(hours: int = 48) -> dict:
    """Re-attribute recent feed killmails so nothing is lost."""
    return attribution.sweep_recent(hours=hours)


@app.task()
def poll_campaign_snapshots() -> dict:
    """Contested percentage, victory points and operational state."""
    result = snapshots.record_snapshots()
    for campaign in _live_campaigns():
        plan.update_week_progress(campaign)
    return result


@app.task()
def poll_campaign_payouts(limit: int = 200) -> dict:
    """Read FW LP payout notifications for every included character.

    Character notifications sit in a 15-token bucket per character per 15
    minutes, so one character costs a fifth of its budget per poll and the
    gate holds the rest back for everything else.
    """
    characters = (
        CampaignEnlistmentCharacter.objects.filter(
            enlistment__status="active",
            enlistment__campaign__status__in=["scheduled", "active"],
            included_until__isnull=True,
        )
        .select_related("character")
        .distinct()[:limit]
    )

    polled = 0
    stored = 0
    skipped = 0

    for row in characters:
        character = row.character
        if character.esi_suspended or character.esi_deleted:
            skipped += 1
            continue
        if not esi_gate.can_spend("char-notification", character.character_id):
            skipped += 1
            continue

        response = EsiClient(character).get_character_notifications()
        esi_gate.spend("char-notification", character.character_id)
        polled += 1

        if not response.success():
            esi_gate.record_error()
            logger.info(
                "Notification poll failed for %s: %s",
                character.character_name,
                response.error_text(),
            )
            continue

        for notification in response.results() or []:
            payout = sites.store_payout(character, notification)
            if payout:
                stored += 1

    attributed = attribute_new_payouts()
    return {
        "polled": polled,
        "stored": stored,
        "skipped": skipped,
        **attributed,
    }


def attribute_new_payouts(hours: int = 72) -> dict:
    """Attribute payouts we have stored but not yet placed in a campaign."""
    since = timezone.now() - timedelta(hours=hours)
    payouts = EveCharacterFwLpPayout.objects.filter(
        occurred_at__gte=since, campaignsitecompletion__isnull=True
    ).select_related("character")
    result = sites.attribute_payouts(payouts)
    result.update(sites.build_complex_completions(since_hours=hours))
    return result


@app.task()
def materialise_campaign_stats() -> dict:
    """Rebuild today's and yesterday's rows, then the roll-ups and ranks."""
    written = 0
    rebuilt = 0
    for campaign in _live_campaigns():
        written += stats.materialise_recent(campaign, days=2)
        rebuilt += stats.rebuild_stats(campaign)
        plan.evaluate_orders(campaign)
    named = names.backfill_victim_names()
    return {
        "days_written": written,
        "stats_rebuilt": rebuilt,
        "names": named,
    }


@app.task()
def mirror_campaign_feed_events() -> dict:
    mirrored = 0
    for campaign in _live_campaigns():
        mirrored += snapshots.mirror_feed_events(campaign)
    return {"mirrored": mirrored}


@app.task()
def propose_campaign_week() -> dict:
    """Thursday 11:00: propose next week's targets for every live campaign."""
    proposed = 0
    for campaign in Campaign.objects.filter(status=CampaignStatus.ACTIVE):
        proposed += plan.propose_week(campaign)
    return {"proposed": proposed}


@app.task()
def generate_campaign_orders() -> dict:
    """Thursday and every day at 11:05: today's orders from the week's gap."""
    created = 0
    for campaign in Campaign.objects.filter(status=CampaignStatus.ACTIVE):
        created += plan.generate_orders(campaign)
        if (
            not campaign.commander_order_text
            or campaign.commander_order_is_draft
        ):
            campaign.commander_order_text = plan.draft_commander_order(
                campaign
            )
            campaign.commander_order_set_at = timezone.now()
            campaign.commander_order_is_draft = True
            campaign.save(
                update_fields=[
                    "commander_order_text",
                    "commander_order_set_at",
                    "commander_order_is_draft",
                ]
            )
    return {"created": created}


@app.task()
def run_campaign_lifecycle() -> dict:
    """Scheduled becomes active on time; active completes at the end.

    A campaign is never allowed to go active without having been scheduled
    first, because attribution has no backfill and the hook has to have been
    live before the fighting started.
    """
    now = timezone.now()
    started = 0
    completed = 0

    for campaign in Campaign.objects.filter(
        status=CampaignStatus.SCHEDULED, start_at__lte=now
    ):
        campaign.status = CampaignStatus.ACTIVE
        campaign.save(update_fields=["status"])
        CampaignEvent.objects.get_or_create(
            campaign=campaign,
            kind=CampaignEvent.Kind.CAMPAIGN_STARTED,
            defaults={
                "occurred_at": now,
                "title": f"{campaign.name} is live",
                "side": "friendly",
            },
        )
        plan.propose_week(campaign)
        plan.generate_orders(campaign)
        started += 1

    for campaign in Campaign.objects.filter(
        status=CampaignStatus.ACTIVE, end_at__lte=now
    ):
        campaign.status = CampaignStatus.COMPLETED
        campaign.save(update_fields=["status"])
        stats.rebuild_stats(campaign)
        CampaignEvent.objects.get_or_create(
            campaign=campaign,
            kind=CampaignEvent.Kind.CAMPAIGN_COMPLETED,
            defaults={
                "occurred_at": now,
                "title": f"{campaign.name} is over",
                "side": "neutral",
            },
        )
        completed += 1

    return {"started": started, "completed": completed}


@app.task()
def campaign_health() -> dict:
    """What the KPI panel reads, and what pages an operator when it slips."""
    day = campaign_day()
    report = {"esi": esi_gate.snapshot(), "campaigns": {}}

    for campaign in _live_campaigns():
        mails = CampaignKillmail.objects.filter(campaign=campaign)
        missing_from_zkill = mails.filter(on_zkillboard=False).count()
        report["campaigns"][campaign.slug] = {
            "killmails": mails.count(),
            "missing_from_zkillboard": missing_from_zkill,
            "sites": campaign.site_completions.count(),
            "enlisted": campaign.enlistments.filter(status="active").count(),
            "active_today": campaign.participant_days.filter(
                day=day, active=True
            ).count(),
        }

    logger.info("Campaign health: %s", report)
    return report
