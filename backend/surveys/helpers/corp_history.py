"""A member's history through alliance (FL33T) corporations, with per-corp
tenure and an Academy→main "graduated" flag. Read-only, cached DB, guarded.
"""

import logging

from django.utils import timezone

from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCorporation

logger = logging.getLogger(__name__)

FL33T_ALLIANCE_ID = 99011978


def _is_academy(name: str, ticker: str) -> bool:
    return (ticker or "").upper() == "L3ARN" or "academy" in (
        name or ""
    ).lower()


def _aggregate_stints(history, now) -> tuple[dict, list]:
    """Aggregate days per corporation across (possibly repeated) stints."""
    agg: dict[int, dict] = {}
    order: list[int] = []
    for i, row in enumerate(history):
        start = row.start_date
        end = history[i + 1].start_date if i + 1 < len(history) else now
        days = max(0, (end - start).days)
        cid = row.corporation_id
        if cid not in agg:
            agg[cid] = {"corporation_id": cid, "days": 0, "first": start}
            order.append(cid)
        agg[cid]["days"] += days
    return agg, order


def _has_graduated(corps) -> bool:
    """Academy stint followed by a non-academy alliance corp."""
    academy_first = None
    for c in corps:
        if c["is_academy"] and academy_first is None:
            academy_first = c["first"]
        elif (
            not c["is_academy"]
            and academy_first is not None
            and c["first"] >= academy_first
        ):
            return True
    return False


def alliance_corp_history(user) -> dict:
    """Return {"corps": [...], "graduated": bool} for the member's time in the
    alliance's corporations, most-tenured first."""
    empty = {"corps": [], "graduated": False}
    try:
        pc = user_primary_character(user)
        if not pc:
            return empty
        alliance_id = getattr(pc, "alliance_id", None) or FL33T_ALLIANCE_ID

        history = list(
            pc.corporation_history.order_by("start_date", "record_id")
        )
        if not history:
            return empty

        agg, order = _aggregate_stints(history, timezone.now())

        # Resolve names/tickers/alliance and keep only alliance corps.
        corp_map = {
            c.corporation_id: c
            for c in EveCorporation.objects.filter(
                corporation_id__in=list(agg.keys())
            ).select_related("alliance")
        }
        corps = []
        for cid in order:
            corp = corp_map.get(cid)
            if not corp or not corp.alliance:
                continue
            if corp.alliance.alliance_id != alliance_id:
                continue
            corps.append(
                {
                    "corporation_id": cid,
                    "name": corp.name,
                    "ticker": corp.ticker or "",
                    "days": agg[cid]["days"],
                    "first": agg[cid]["first"],
                    "is_current": cid == pc.corporation_id,
                    "is_academy": _is_academy(corp.name, corp.ticker),
                }
            )

        graduated = _has_graduated(corps)

        # Order most-tenured first, drop the internal sort key.
        corps.sort(key=lambda c: c["days"], reverse=True)
        for c in corps:
            c.pop("first", None)
        return {"corps": corps, "graduated": graduated}
    except Exception:  # pragma: no cover - defensive
        logger.debug("alliance_corp_history failed", exc_info=True)
        return empty
