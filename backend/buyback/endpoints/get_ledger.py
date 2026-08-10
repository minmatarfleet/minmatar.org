"""GET /ledger – buyback stock movements."""

from ninja import Query, Router

from buyback.endpoints.schemas import (
    BuybackLedgerEntryResponse,
    BuybackLedgerResponse,
)
from buyback.helpers.valuation import batch_estimate_guide_isk
from buyback.models import BuybackLedgerEntry

router = Router(tags=["Buyback"])

_VALID_REASONS = {choice.value for choice in BuybackLedgerEntry.Reason}


@router.get(
    "/ledger",
    description="Buyback stock ledger movements (in / sold / unknown).",
    response=BuybackLedgerResponse,
)
def get_ledger(
    request,
    reason: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    qs = BuybackLedgerEntry.objects.select_related("eve_type").order_by(
        "-occurred_at", "-id"
    )
    if reason:
        reasons = [part.strip() for part in reason.split(",") if part.strip()]
        reasons = [r for r in reasons if r in _VALID_REASONS]
        if reasons:
            qs = qs.filter(reason__in=reasons)

    count = qs.count()
    page = list(qs[offset : offset + limit])
    estimates = batch_estimate_guide_isk(
        [
            (entry.eve_type_id, entry.eve_type.name, int(entry.quantity))
            for entry in page
        ]
    )

    entries = []
    for entry, estimate in zip(page, estimates):
        recorded = (
            float(entry.isk_total) if entry.isk_total is not None else None
        )
        entries.append(
            BuybackLedgerEntryResponse(
                id=entry.pk,
                reason=entry.reason,
                type_id=entry.eve_type_id,
                name=entry.eve_type.name,
                quantity=int(entry.quantity),
                occurred_at=entry.occurred_at.isoformat(),
                unit_price=(
                    float(entry.unit_price)
                    if entry.unit_price is not None
                    else None
                ),
                isk_total=recorded,
                isk_value=recorded if recorded is not None else estimate,
                source_id=entry.source_id,
                location_id=entry.location_id,
                counterparty_id=entry.counterparty_id,
                counterparty_name=entry.counterparty_name or None,
                counterparty_kind=entry.counterparty_kind or None,
            )
        )
    return BuybackLedgerResponse(entries=entries, count=count)
