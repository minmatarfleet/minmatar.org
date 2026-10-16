"""Scheduled work for campaigns.

Nothing here is the only path to a fact. The stream attributes kills as they
land, the sweep re-attributes the last two days, the recent-killmails poll
recovers a mail the stream missed, the payout poll finds site completions
and the cross-check confirms we did not miss a kill.
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
    frontlines,
    names,
    plan,
    sites,
    snapshots,
    stats,
)
from eveonline.client import EsiClient
from eveonline.models import EveCharacterFwLpPayout
from eveonline.utils import get_esi_downtime_countdown
from feed.helpers.ingest import upsert_feed_killmail_from_raw
from feed.models import FeedKillmail

logger = logging.getLogger(__name__)


def _live_campaigns():
    return Campaign.objects.filter(
        status__in=[CampaignStatus.SCHEDULED, CampaignStatus.ACTIVE]
    )


def _included_character_rows(order_field: str):
    """Active enlisted characters, least-recently polled first."""
    return (
        CampaignEnlistmentCharacter.objects.filter(
            enlistment__status="active",
            enlistment__campaign__status__in=["scheduled", "active"],
            included_until__isnull=True,
        )
        .select_related("character")
        .order_by(F(order_field).asc(nulls_first=True))
    )


def _defer_for_downtime(kind: str) -> dict | None:
    """Skip an ESI poll that would run across the 11:00 UTC downtime."""
    countdown = get_esi_downtime_countdown()
    if countdown <= 0:
        return None
    logger.info("Skipping %s poll during ESI downtime (%ss)", kind, countdown)
    return {"polled": 0, "stored": 0, "skipped": 0, "deferred": countdown}


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
    result["advantage"] = frontlines.record_advantage()
    for campaign in _live_campaigns():
        plan.update_week_progress(campaign)
    return result


@app.task()
def poll_frontlines_advantage() -> dict:
    """Advantage per system, read off CCP's frontlines page instead of pilots."""
    result = frontlines.record_advantage()
    # Contested is on a slower poll. A system with no snapshot yet would
    # sit on "not yet pulled" until that poll, so fill those in here.
    if snapshots.fw_systems_without_snapshots().exists():
        filled = snapshots.record_snapshots()
        result["snapshots"] = filled["written"]
    # An advantage target is measured against this number, so the week's
    # pace has to move with it.
    if result.get("written"):
        for campaign in _live_campaigns():
            plan.update_week_progress(campaign)
    return result


@app.task()
def poll_campaign_payouts(limit: int | None = None) -> dict:
    """Read FW LP payout notifications for every included character.

    Character notifications sit in a 15-token bucket per character per 15
    minutes. The shared gate is the stop: a paused character is skipped and
    the rest of the roster is still read. ``limit`` is an operator cap.
    """
    deferred = _defer_for_downtime("payout")
    if deferred is not None:
        return deferred

    polled = 0
    stored = 0
    skipped = 0
    seen: set[int] = set()

    for row in _included_character_rows("payouts_polled_at").iterator():
        character = row.character
        # A pilot can have the same character in two campaigns; ESI does not
        # care, and neither should our budget.
        if character.character_id in seen:
            continue
        if limit is not None and polled >= limit:
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

        esi_gate.note_response(
            "char-notification", character.character_id, response
        )
        polled += 1

        if response.response_code == 304 or not response.success():
            if not response.success():
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

    _apply_seeded_event_codes()
    attributed = attribute_new_payouts()
    return {
        "polled": polled,
        "stored": stored,
        "skipped": skipped,
        **attributed,
    }


@app.task()
def poll_campaign_recent_killmails(limit: int | None = None) -> dict:
    """Fetch recent killmails for enlisted characters the feed does not have.

    The stream is still the fast path. This poll only asks ESI for mails
    missing from ``FeedKillmail``, then hands them to the same ingest path
    the stream uses. Known ids are the cache; django-esi ETags stay off.
    """
    deferred = _defer_for_downtime("recent killmail")
    if deferred is not None:
        return deferred

    polled = 0
    fetched = 0
    ingested = 0
    skipped = 0
    seen: set[int] = set()

    for row in _included_character_rows("killmails_polled_at").iterator():
        character = row.character
        if character.character_id in seen:
            continue
        if limit is not None and polled >= limit:
            break
        if character.esi_suspended or character.esi_deleted:
            skipped += 1
            continue
        if not esi_gate.can_spend("char-killmail", character.character_id):
            skipped += 1
            continue

        seen.add(character.character_id)
        CampaignEnlistmentCharacter.objects.filter(character=character).update(
            killmails_polled_at=timezone.now()
        )

        try:
            response = EsiClient(character).get_recent_killmails()
        except Exception:  # pragma: no cover - one bad row, not the batch
            logger.exception(
                "Recent killmail poll raised for %s", character.character_name
            )
            esi_gate.record_error()
            continue

        esi_gate.note_response(
            "char-killmail", character.character_id, response
        )
        polled += 1
        if not response.success():
            logger.info(
                "Recent killmail poll failed for %s: %s",
                character.character_name,
                response.error_text(),
            )
            continue

        found = _ingest_missing_killmails(character, response.results() or [])
        fetched += found["fetched"]
        ingested += found["ingested"]
        skipped += found["skipped"]

    return {
        "polled": polled,
        "fetched": fetched,
        "ingested": ingested,
        "skipped": skipped,
    }


def _ingest_missing_killmails(character, entries: list) -> dict:
    """Fetch ESI details for recent mails the feed has not stored yet."""
    fetched = 0
    ingested = 0
    skipped = 0
    for entry in entries:
        killmail_id, killmail_hash = _recent_killmail_identity(entry)
        if killmail_id is None:
            continue
        if FeedKillmail.objects.filter(killmail_id=killmail_id).exists():
            continue
        if not esi_gate.can_spend("killmail"):
            skipped += 1
            break
        stored = _fetch_and_ingest_killmail(
            character, killmail_id, killmail_hash
        )
        if stored is None:
            continue
        fetched += 1
        if stored:
            ingested += 1
    return {"fetched": fetched, "ingested": ingested, "skipped": skipped}


def _fetch_and_ingest_killmail(
    character, killmail_id: int, killmail_hash: str
):
    """One public killmail fetch. None when the call failed, else ingested."""
    try:
        detail = EsiClient(character).get_character_killmail(
            killmail_id, killmail_hash
        )
    except Exception:  # pragma: no cover
        logger.exception(
            "Killmail %s fetch raised for %s",
            killmail_id,
            character.character_name,
        )
        esi_gate.record_error()
        return None

    esi_gate.note_response("killmail", None, detail)
    if not detail.success():
        return None
    raw = detail.results()
    if not isinstance(raw, dict):
        return None
    raw = dict(raw)
    raw.setdefault("killmail_id", killmail_id)
    stored = upsert_feed_killmail_from_raw(
        raw,
        zkb_meta={"hash": killmail_hash},
        source="esi",
    )
    return stored is not None


def _recent_killmail_identity(entry) -> tuple[int | None, str | None]:
    if not isinstance(entry, dict):
        return None, None
    killmail_hash = entry.get("killmail_hash") or entry.get("hash")
    if not killmail_hash:
        return None, None
    try:
        return int(entry.get("killmail_id")), str(killmail_hash)
    except (TypeError, ValueError):
        return None, None


def _apply_seeded_event_codes() -> None:
    """Seed payout codes the migration has not reached, then relabel sites.

    A code that was still unknown when its completions were stored gets its
    name here. A human confirmation is never overwritten.
    """
    if sites.seed_event_codes():
        sites.rescore_completions()


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
