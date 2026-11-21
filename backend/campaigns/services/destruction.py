"""The Destruction tab: what the campaign's pilots killed, and its tallies."""

from __future__ import annotations

from django.db.models import Max, Sum

from campaigns.helpers import campaign_week_start
from campaigns.models import Campaign, CampaignKillmail, KillmailOutcome
from campaigns.services.tickers import alliance_tickers
from eveuniverse.models import EveType


def destruction(campaign: Campaign, limit: int = 50) -> dict:
    kills = CampaignKillmail.objects.filter(
        campaign=campaign, outcome=KillmailOutcome.KILL
    )
    mails = list(kills.select_related("structure")[:limit])
    type_names = dict(
        EveType.objects.filter(
            id__in={mail.victim_ship_type_id for mail in mails}
        ).values_list("id", "name")
    )
    tickers = alliance_tickers(
        (mail.victim_alliance_id for mail in mails), campaign
    )
    return {
        "isk_destroyed_week": kills.filter(
            killmail_time__gte=campaign_week_start()
        ).aggregate(v=Sum("isk_value"))["v"]
        or 0,
        "structures_destroyed": campaign.structures.filter(
            status="destroyed"
        ).count(),
        "biggest_kill_isk": kills.aggregate(v=Max("isk_value"))["v"] or 0,
        "rows": [
            {
                "killmail_id": mail.killmail_id,
                "killmail_time": mail.killmail_time,
                "type_id": mail.victim_ship_type_id,
                "name": (
                    mail.structure.name
                    if mail.structure_id
                    else type_names.get(mail.victim_ship_type_id, "")
                ),
                "type_name": type_names.get(mail.victim_ship_type_id, ""),
                "alliance_id": mail.victim_alliance_id,
                "alliance_ticker": tickers.get(mail.victim_alliance_id, ""),
                "isk_value": mail.isk_value,
                "is_structure": mail.is_structure,
            }
            for mail in mails
        ],
    }
