"""Buyback stockpile overview metrics."""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from eveuniverse.models import EveType

from buyback.helpers.valuation import batch_estimate_guide_isk
from buyback.models import (
    BUYBACK_CORPORATION_ID,
    BuybackAcceptedItem,
    BuybackHangarSnapshot,
    BuybackLedgerEntry,
)
from eveonline.client import EsiClient
from eveonline.helpers.corporations import (
    SCOPE_CORPORATION_WALLET,
    get_director_with_scope,
)
from eveonline.models import EveCorporation

logger = logging.getLogger(__name__)

TURNOVER_WINDOW_DAYS = 30
SALE_REASONS = (
    BuybackLedgerEntry.Reason.SOLD_ORDER,
    BuybackLedgerEntry.Reason.SOLD_CONTRACT,
)


def hangar_quantities() -> dict[int, int]:
    """Latest hangar snapshot quantities, else accepted-item stockpile fields."""
    snapshot = BuybackHangarSnapshot.objects.order_by("-taken_at").first()
    quantities: dict[int, int] = {}
    if snapshot is not None:
        for key, qty in (snapshot.quantities or {}).items():
            try:
                quantities[int(key)] = int(qty)
            except (TypeError, ValueError):
                continue
        return quantities

    for type_id, qty in BuybackAcceptedItem.objects.filter(
        active=True
    ).values_list("eve_type_id", "stockpile_quantity"):
        quantities[int(type_id)] = int(qty or 0)
    return quantities


def compute_stockpile_value() -> int:
    quantities = hangar_quantities()
    rows: list[tuple[int, str, int]] = []
    type_ids = [type_id for type_id, qty in quantities.items() if qty > 0]
    names = {
        eve_type.id: eve_type.name
        for eve_type in EveType.objects.filter(id__in=type_ids)
    }
    for type_id in type_ids:
        name = names.get(type_id)
        if not name:
            continue
        rows.append((type_id, name, quantities[type_id]))
    totals = batch_estimate_guide_isk(rows)
    return int(round(sum(value for value in totals if value is not None)))


def fetch_corporation_wallet_balance() -> int | None:
    """Sum of M-EXC wallet division balances, or None if ESI unavailable."""
    try:
        corp = EveCorporation.objects.get(
            corporation_id=BUYBACK_CORPORATION_ID
        )
    except EveCorporation.DoesNotExist:
        logger.warning("M-EXC corporation %s missing", BUYBACK_CORPORATION_ID)
        return None
    character = get_director_with_scope(corp, SCOPE_CORPORATION_WALLET)
    if character is None:
        logger.warning("No director with corp wallet scope for M-EXC")
        return None
    response = EsiClient(character).get_corporation_wallets(
        BUYBACK_CORPORATION_ID
    )
    if not response.success():
        logger.warning("Corp wallets ESI failed: %s", response.response_code)
        return None
    total = Decimal("0")
    for row in response.results() or []:
        balance = row.get("balance")
        if balance is None:
            continue
        total += Decimal(str(balance))
    return int(total)


def compute_turnover_value(*, window_days: int = TURNOVER_WINDOW_DAYS) -> int:
    """ISK out via sold_order / sold_contract over the window."""
    since = timezone.now() - timedelta(days=window_days)
    entries = list(
        BuybackLedgerEntry.objects.filter(
            reason__in=SALE_REASONS,
            occurred_at__gte=since,
        ).select_related("eve_type")
    )
    recorded = Decimal("0")
    missing_rows: list[tuple[int, str, int]] = []
    for entry in entries:
        if entry.isk_total is not None:
            recorded += Decimal(entry.isk_total)
            continue
        missing_rows.append(
            (entry.eve_type_id, entry.eve_type.name, int(entry.quantity))
        )
    estimates = batch_estimate_guide_isk(missing_rows)
    estimated = sum(
        (Decimal(str(value)) for value in estimates if value is not None),
        Decimal("0"),
    )
    return int(round(recorded + estimated))


def compute_stock_stats() -> dict:
    return {
        "stockpile_value": compute_stockpile_value(),
        "remaining_isk": fetch_corporation_wallet_balance(),
        "turnover_value": compute_turnover_value(),
        "window_days": TURNOVER_WINDOW_DAYS,
    }
