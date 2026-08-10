"""Hangar snapshots and Unknown residual ledger rows."""

from __future__ import annotations

import logging
from datetime import datetime

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from eveuniverse.models import EveType

from buyback.helpers.hangar import fetch_stockpile_quantities
from buyback.models import (
    BuybackHangarSnapshot,
    BuybackLedgerEntry,
    EveBuybackSettings,
)

logger = logging.getLogger(__name__)

UNKNOWN_QTY_THRESHOLD = 1


def _quantities_for_json(quantities: dict[int, int]) -> dict[str, int]:
    return {str(type_id): int(qty) for type_id, qty in quantities.items()}


def _quantities_from_json(raw: dict) -> dict[int, int]:
    result: dict[int, int] = {}
    for key, qty in (raw or {}).items():
        try:
            result[int(key)] = int(qty)
        except (TypeError, ValueError):
            continue
    return result


def take_hangar_snapshot(
    *,
    settings: EveBuybackSettings | None = None,
    taken_at: datetime | None = None,
    quantities: dict[int, int] | None = None,
) -> BuybackHangarSnapshot:
    qty = (
        quantities
        if quantities is not None
        else fetch_stockpile_quantities(settings=settings)
    )
    return BuybackHangarSnapshot.objects.create(
        taken_at=taken_at or timezone.now(),
        quantities=_quantities_for_json(qty),
    )


def _ledger_sum_by_type(
    *,
    reasons: list[str],
    after: datetime,
    until: datetime,
) -> dict[int, int]:
    rows = (
        BuybackLedgerEntry.objects.filter(
            reason__in=reasons,
            occurred_at__gt=after,
            occurred_at__lte=until,
        )
        .values("eve_type_id")
        .annotate(total=Sum("quantity"))
    )
    return {int(row["eve_type_id"]): int(row["total"] or 0) for row in rows}


@transaction.atomic
def emit_unknown_from_snapshots(
    previous: BuybackHangarSnapshot,
    current: BuybackHangarSnapshot,
) -> dict[str, int]:
    """
    Compare two hangar snapshots and create unknown outs for unexplained drops.

    expected = qty_T0 + in_contract - sold_order - sold_contract  (in window)
    unknown_qty = max(0, expected - qty_T1)
    """
    qty_t0 = _quantities_from_json(previous.quantities)
    qty_t1 = _quantities_from_json(current.quantities)
    t0 = previous.taken_at
    t1 = current.taken_at

    explained_in = _ledger_sum_by_type(
        reasons=[BuybackLedgerEntry.Reason.IN_CONTRACT],
        after=t0,
        until=t1,
    )
    explained_out = _ledger_sum_by_type(
        reasons=[
            BuybackLedgerEntry.Reason.SOLD_ORDER,
            BuybackLedgerEntry.Reason.SOLD_CONTRACT,
        ],
        after=t0,
        until=t1,
    )

    type_ids = (
        set(qty_t0) | set(qty_t1) | set(explained_in) | set(explained_out)
    )
    created = 0
    for type_id in type_ids:
        expected = (
            qty_t0.get(type_id, 0)
            + explained_in.get(type_id, 0)
            - explained_out.get(type_id, 0)
        )
        unknown_qty = max(0, expected - qty_t1.get(type_id, 0))
        if unknown_qty < UNKNOWN_QTY_THRESHOLD:
            continue
        try:
            eve_type = EveType.objects.get(id=type_id)
        except EveType.DoesNotExist:
            logger.warning(
                "Unknown residual skipped; missing type %s", type_id
            )
            continue
        source_id = f"{previous.pk}:{current.pk}:{type_id}"
        _, was_created = BuybackLedgerEntry.objects.update_or_create(
            reason=BuybackLedgerEntry.Reason.UNKNOWN,
            source_id=source_id,
            eve_type=eve_type,
            defaults={
                "quantity": unknown_qty,
                "occurred_at": t1,
                "unit_price": None,
                "isk_total": None,
                "location_id": None,
            },
        )
        if was_created:
            created += 1
    return {"types_checked": len(type_ids), "created": created}
