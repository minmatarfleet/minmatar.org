"""Scheduled work for campaigns.

Nothing here is the only path to a fact. The stream attributes kills as they
land, the sweep re-attributes the last two days, the payout poll finds site
completions and the cross-check confirms we did not miss a kill.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db.models import F
from django.utils import timezone

from app.celery import app
from campaigns.helpers import campaign_day, campaign_week_start
from campaigns.models import (
    Campaign,
    CampaignEnlistmentCharacter,
    CampaignEvent,
    CampaignKillmail,
    CampaignStatus,
)
from campaigns.services import (
    attribution,
    awards,
    esi_gate,
    fleets,
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
def sweep_campaign_killmails(hours: int = 4) -> dict:
    """Re-attribute recent feed killmails so nothing is lost.

    The frequent pass only needs to cover the stream's catch-up lag. The
    deep pass below covers the two days the plan asks for, where a character
    changing hands or a late enlistment can still change an outcome.
    """
    return attribution.sweep_recent(hours=hours)


@app.task()
def deep_sweep_campaign_killmails() -> dict:
    """Hourly 48-hour re-attribution, the plan's safety net."""
    return attribution.sweep_recent(hours=48)


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
    # Least-recently-polled first, so a campaign larger than one batch still
    # gets every character read instead of the same alphabetical prefix.
    rows = (
        CampaignEnlistmentCharacter.objects.filter(
            enlistment__status="active",
            enlistment__campaign__status__in=["scheduled", "active"],
            included_until__isnull=True,
        )
        .select_related("character")
        .order_by(F("payouts_polled_at").asc(nulls_first=True))
    )

    polled = 0
    stored = 0
    skipped = 0
    seen: set[int] = set()

    for row in rows.iterator():
        character = row.character
        # A pilot can have the same character in two campaigns; ESI does not
        # care, and neither should our budget.
        if character.character_id in seen:
            continue
        if polled >= limit:
            break
        if character.esi_suspended or character.esi_deleted:
            skipped += 1
            continue
        if not esi_gate.can_spend("char-notification", character.character_id):
            skipped += 1
            continue

        seen.add(character.character_id)
        CampaignEnlistmentCharacter.objects.filter(character=character).update(
            payouts_polled_at=timezone.now()
        )

        try:
            response = EsiClient(character).get_character_notifications()
        except Exception:  # pragma: no cover - one bad row, not the batch
            logger.exception(
                "Notification poll raised for %s", character.character_name
            )
            esi_gate.record_error()
            continue

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
    result.update(sites.build_complex_completions(since_hours=6))
    return result


@app.task()
def link_campaign_fleets() -> dict:
    """Attach campaign mails to the fleet their pilots were flying in."""
    linked = 0
    for campaign in _live_campaigns():
        fleets.refresh_standing_fleet(campaign)
        for offset in range(2):
            linked += fleets.link_killmails_to_fleets(
                campaign, campaign_day() - timedelta(days=offset)
            )
    return {"linked": linked}


@app.task()
def materialise_campaign_stats() -> dict:
    """Rebuild today's and yesterday's rows, then the roll-ups and ranks."""
    written = 0
    rebuilt = 0
    for campaign in _live_campaigns():
        # Two passes: the first gives the orders something to be judged on,
        # the second folds the completed orders back into the day's points.
        stats.materialise_recent(campaign, days=2)
        plan.evaluate_orders(campaign)
        written += stats.materialise_recent(campaign, days=2)
        rebuilt += stats.rebuild_stats(campaign)
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
def close_campaign_week() -> dict:
    """Thursday: freeze last week and hand out its six awards."""
    awarded = 0
    for campaign in Campaign.objects.filter(status=CampaignStatus.ACTIVE):
        last_week = campaign_week_start() - timedelta(days=7)
        stats.materialise_recent(campaign, days=9)
        awarded += awards.close_week(campaign, last_week)
    return {"awarded": awarded}


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
        awards.close_week(campaign)
        awards.close_campaign(campaign)
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
