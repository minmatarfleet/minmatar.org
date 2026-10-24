"""Doctrine fits members sold on contract (Market tribe)."""

from __future__ import annotations

from collections import Counter, defaultdict

from django.db.models.functions import Coalesce
from eveuniverse.models import EveType

from market.models import EveMarketContract
from tribes.reports.queries.common import (
    best_month,
    best_month_since,
    characters_to_users,
    next_milestone,
    period_window,
    person_rows,
    roster_characters_by_eve_id,
)
from tribes.reports.roster import roster_user_ids
from tribes.reports.types import PeriodBounds, ReportScope

COLUMNS = [
    "primary_character_name",
    "fits_sold",
    "isk_sold",
    "fits_listed",
]

HULL_TILES = 6


def _sold_contracts():
    """
    Finished doctrine-fit contracts with the moment they sold.

    Public contracts that vanish before expiry are marked finished without a
    completed_at (only token-synced contracts carry one), so last_updated
    stands in. A contract its issuer deleted looks the same, so these counts
    are "sold" in the loose sense.
    """
    return EveMarketContract.objects.filter(
        status="finished", fitting__isnull=False
    ).annotate(sold_at=Coalesce("completed_at", "last_updated"))


def _issuer_map(tribe_group, scope: ReportScope) -> dict[int, int] | None:
    if scope == ReportScope.ROSTER:
        return roster_characters_by_eve_id(roster_user_ids(tribe_group))
    return None


def run_market_sales_report(
    tribe_group, period: PeriodBounds, scope: ReportScope, params
):
    start, end = period_window(period)
    issuers = _issuer_map(tribe_group, scope)
    if issuers is not None and not issuers:
        return [], _empty_totals(), COLUMNS

    sold = _sold_contracts().filter(sold_at__gte=start, sold_at__lte=end)
    listed = EveMarketContract.objects.filter(
        fitting__isnull=False, issued_at__gte=start, issued_at__lte=end
    )
    if issuers is not None:
        sold = sold.filter(issuer_external_id__in=issuers)
        listed = listed.filter(issuer_external_id__in=issuers)

    sold_rows = list(
        sold.values_list("issuer_external_id", "price", "completed_at")
    )
    listed_rows = list(listed.values_list("issuer_external_id", flat=True))
    if issuers is None:
        issuers = characters_to_users(
            {row[0] for row in sold_rows} | set(listed_rows)
        )

    by_user: dict[int, dict] = defaultdict(
        lambda: {"fits_sold": 0, "isk_sold": 0.0, "fits_listed": 0}
    )
    confirmed = 0
    for issuer, price, completed_at in sold_rows:
        user_id = issuers.get(issuer)
        if user_id is None:
            continue
        by_user[user_id]["fits_sold"] += 1
        by_user[user_id]["isk_sold"] += float(price or 0)
        if completed_at is not None:
            confirmed += 1
    for issuer in listed_rows:
        user_id = issuers.get(issuer)
        if user_id is not None:
            by_user[user_id]["fits_listed"] += 1

    rows = person_rows(by_user, "fits_sold")
    totals = {
        "fits_sold": sum(r["fits_sold"] for r in rows),
        "isk_sold": sum(r["isk_sold"] for r in rows),
        "fits_listed": sum(r["fits_listed"] for r in rows),
        "sellers": sum(1 for r in rows if r["fits_sold"]),
        "confirmed_sales": confirmed,
    }
    return rows, totals, COLUMNS


def market_sales_highlights(tribe_group, period: PeriodBounds) -> dict:
    """Hulls sold this period, best month and the all-time milestone."""
    start, end = period_window(period)
    issuers = roster_characters_by_eve_id(roster_user_ids(tribe_group))
    if not issuers:
        return {}
    sold = _sold_contracts().filter(issuer_external_id__in=issuers)

    hull_counts = Counter(
        sold.filter(sold_at__gte=start, sold_at__lte=end).values_list(
            "fitting__ship_id", flat=True
        )
    )
    top = hull_counts.most_common(HULL_TILES)
    names = dict(
        EveType.objects.filter(id__in=[t for t, _ in top]).values_list(
            "id", "name"
        )
    )
    all_time = sold.count()
    return {
        "hulls": [
            {"type_id": type_id, "name": names.get(type_id, ""), "count": n}
            for type_id, n in top
        ],
        "best_month": best_month(
            (stamp, 1)
            for stamp in sold.filter(
                sold_at__gte=best_month_since()
            ).values_list("sold_at", flat=True)
        ),
        "all_time": {
            "fits_sold": all_time,
            "next_milestone": next_milestone(all_time),
        },
    }


def _empty_totals():
    return {
        "fits_sold": 0,
        "isk_sold": 0.0,
        "fits_listed": 0,
        "sellers": 0,
        "confirmed_sales": 0,
    }
