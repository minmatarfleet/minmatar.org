"""Which alliances and corporations count as "ours".

There are three legitimate scopes; pick one explicitly at each call site.

- Member alliances: FL33T and the Associates (BUILD). Membership, managed
  corporation pages, corp refresh tasks. Fixed IDs from eveonline.constants,
  so an in-game rename or an extra EveAlliance row never changes them.
- Alliance corporations: FL33T only. Alliance health and officer access use
  this without the holding corporation (HOLDING_CORPORATION_TICKER).
- Tracked alliances: every EveAlliance row. Admins add these rows to say
  "sync this alliance"; EveCorporation.alliance is only set for them. Use it
  for syncing and for "our pilots" data sweeps (structures, assets, losses).
"""

from eveonline.constants import (
    FL33T_MEMBER_ALLIANCE_IDS,
    HOLDING_CORPORATION_TICKER,
    MINMATAR_FLEET_ALLIANCE_ID,
)
from eveonline.models import EveAlliance, EveCorporation


def member_alliance_ids() -> frozenset[int]:
    """FL33T + BUILD alliance IDs."""
    return FL33T_MEMBER_ALLIANCE_IDS


def tracked_alliance_ids() -> set[int]:
    """Alliance IDs of every EveAlliance row (the alliances we sync)."""
    return set(EveAlliance.objects.values_list("alliance_id", flat=True))


def member_corporations():
    """Corporations in FL33T or BUILD."""
    return EveCorporation.objects.filter(
        alliance__alliance_id__in=FL33T_MEMBER_ALLIANCE_IDS
    )


def alliance_corporations(*, include_holding_corporation: bool = True):
    """Corporations in FL33T, optionally without the holding corporation."""
    corporations = EveCorporation.objects.filter(
        alliance__alliance_id=MINMATAR_FLEET_ALLIANCE_ID
    )
    if not include_holding_corporation:
        corporations = corporations.exclude(ticker=HOLDING_CORPORATION_TICKER)
    return corporations
