"""Pull fresh live data for one campaign on demand.

The scheduled tasks do this for every live campaign. Settings exposes the
same work for the campaign an operator is looking at.
"""

from __future__ import annotations

from datetime import timedelta

from campaigns.helpers import campaign_day
from campaigns.models import Campaign
from campaigns.services import attribution, frontlines, plan, snapshots, stats
from campaigns.services import fleets as fleet_service


def refresh_campaign(campaign: Campaign) -> dict:
    """Re-attribute kills, record faction warfare, and rebuild recent boards.

    Covers every non-retired system in the theater, not only systems that
    already have a snapshot.
    """
    # Contested is the figure the system cards were missing. Pull it before
    # the killmail sweep so a sweep error cannot skip it, and ignore the
    # shared ESI budget: an operator just asked for this campaign.
    fw = snapshots.record_snapshots(campaign, force=True)
    kills = attribution.sweep_campaign(campaign)
    advantage = frontlines.record_advantage(campaign=campaign, force=True)
    progress = plan.update_week_progress(campaign)
    today = campaign_day()
    days = stats.materialise_recent(campaign, days=2)
    rebuilt = stats.rebuild_stats(campaign)
    orders = plan.evaluate_orders(campaign, today)
    linked = 0
    for offset in range(2):
        linked += fleet_service.link_killmails_to_fleets(
            campaign, today - timedelta(days=offset)
        )
    return {
        "killmails_scanned": kills["scanned"],
        "killmails_attributed": kills["attributed"],
        "snapshots": fw["written"],
        "snapshots_missing": fw.get("missing", []),
        "theater_systems": fw.get("systems", 0),
        "advantage": advantage["written"],
        "week_targets": progress,
        "days": days,
        "stats": rebuilt,
        "orders": orders,
        "fleets": linked,
    }
