"""The campaign timerboard: every structure timer tied to a campaign.

A timer belongs to a campaign when it is linked directly
(``EveStructureTimer.campaign``) or through a recon row
(``CampaignStructure.timer``). Each one gets its reinforcement stage: three
chevrons for shield, armor and hull, filled up to the stage the timer
starts, and whether it is the final timer, when the structure dies.
"""

from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from campaigns.models import Campaign, CampaignStructure, StructureStatus
from campaigns.services.tickers import alliance_tickers, owner_alliance
from structures.models import EveStructureTimer

# One reinforcement: shield down, one timer, then the kill. Every timer of
# these is the final one (stage 3).
ONE_REINFORCEMENT = {"armor": 3, "hull": 3}
# Two reinforcements: the armor timer (stage 2) is followed by a hull
# timer (stage 3), which is the final one.
TWO_REINFORCEMENTS = {"armor": 2, "hull": 3}

# The stage each timer starts, by structure type and timer state. The one
# place to correct when CCP changes a structure's reinforcement cycle.
TIMER_STAGES = {
    # Medium Upwell structures
    "astrahus": ONE_REINFORCEMENT,
    "raitaru": ONE_REINFORCEMENT,
    "athanor": ONE_REINFORCEMENT,
    # Sovereignty-free deployables and starbases
    "orbital_skyhook": ONE_REINFORCEMENT,
    "metenox_moon_drill": ONE_REINFORCEMENT,
    "player_owned_customs_office": ONE_REINFORCEMENT,
    "player_owned_starbase": ONE_REINFORCEMENT,
    "mercenary_den": ONE_REINFORCEMENT,
    # Large and XL Upwell structures
    "fortizar": TWO_REINFORCEMENTS,
    "azbel": TWO_REINFORCEMENTS,
    "tatara": TWO_REINFORCEMENTS,
    "keepstar": TWO_REINFORCEMENTS,
    "sotiyo": TWO_REINFORCEMENTS,
    # FLEX structures
    "ansiblex_jump_gate": TWO_REINFORCEMENTS,
    "pharolux_cyno_beacon": TWO_REINFORCEMENTS,
    "tenebrex_cyno_jammer": TWO_REINFORCEMENTS,
}
FINAL_STAGE = 3

TYPE_NAMES = dict(CampaignStructure.TYPE_CHOICES)


def timer_stage(structure_type: str, state: str) -> tuple[int, bool]:
    """(stage, final). An anchoring or unanchoring timer is stage 1: the
    structure is not under attack, so nothing dies when it runs out."""
    stages = TIMER_STAGES.get(structure_type, TWO_REINFORCEMENTS)
    stage = stages.get(state, 1)
    return stage, stage == FINAL_STAGE


def campaign_timers(campaign: Campaign) -> list[dict]:
    """Upcoming timers soonest first, then finished ones newest first."""
    structures = {
        structure.timer_id: structure
        for structure in campaign.structures.filter(timer__isnull=False)
    }
    timers = list(
        EveStructureTimer.objects.filter(
            Q(campaign=campaign) | Q(id__in=list(structures))
        ).distinct()
    )
    tickers = alliance_tickers(
        (owner_alliance(s)[0] for s in structures.values()), campaign
    )
    now = timezone.now()
    rows = [_row(timer, structures.get(timer.id), tickers) for timer in timers]
    upcoming = sorted(
        (row for row in rows if row["at"] > now), key=lambda row: row["at"]
    )
    done = sorted(
        (row for row in rows if row["at"] <= now),
        key=lambda row: row["at"],
        reverse=True,
    )
    for row in done:
        row["done"] = True
    return upcoming + done


def next_timers(campaign: Campaign, limit: int = 3) -> list[dict]:
    return [row for row in campaign_timers(campaign) if not row["done"]][
        :limit
    ]


def _row(timer, structure, tickers: dict) -> dict:
    stage, final = timer_stage(timer.type, timer.state)
    alliance_id, alliance_name = (
        owner_alliance(structure)
        if structure
        else (None, timer.alliance_name or "")
    )
    destroyed = bool(
        structure and structure.status == StructureStatus.DESTROYED
    )
    if destroyed:
        outcome = "destroyed"
    elif final:
        outcome = "survived"
    else:
        outcome = "passed"
    return {
        "id": timer.id,
        "name": structure.name if structure else timer.name,
        "structure_type": timer.type,
        "type_name": TYPE_NAMES.get(timer.type, timer.type),
        "type_id": structure.type_id if structure else None,
        "system": timer.system_name,
        "state": timer.state,
        "stage": stage,
        "final": final,
        "at": timer.timer,
        "alliance_id": alliance_id,
        "alliance_ticker": tickers.get(alliance_id, "") or alliance_name,
        "done": False,
        "outcome": outcome,
    }
