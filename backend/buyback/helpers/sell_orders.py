"""Sync corp market sell fills into sold_order ledger rows."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from eveuniverse.models import EveType

from buyback.helpers.counterparty import resolve_counterparties
from buyback.models import BUYBACK_CORPORATION_ID, BuybackLedgerEntry
from eveonline.client import EsiClient
from eveonline.helpers.corporations import (
    SCOPE_CORPORATION_WALLET,
    get_director_with_scope,
)
from eveonline.models import EveCorporation

logger = logging.getLogger(__name__)


def _as_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            return timezone.make_aware(value, timezone.utc)
        return value
    parsed = parse_datetime(str(value))
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.utc)
    return parsed


def fetch_wallet_transactions() -> list[dict]:
    try:
        corp = EveCorporation.objects.get(
            corporation_id=BUYBACK_CORPORATION_ID
        )
    except EveCorporation.DoesNotExist:
        return []
    character = get_director_with_scope(corp, SCOPE_CORPORATION_WALLET)
    if character is None:
        logger.warning("No director with corp wallet scope for M-EXC")
        return []
    response = EsiClient(character).get_corporation_wallet_transactions(
        BUYBACK_CORPORATION_ID
    )
    if not response.success():
        logger.warning(
            "Wallet transactions ESI failed: %s", response.response_code
        )
        return []
    return list(response.results() or [])


def _ensure_type(type_id: int) -> EveType | None:
    try:
        eve_type = EveType.objects.filter(id=type_id).first()
        if eve_type is not None:
            return eve_type
        eve_type, _ = EveType.objects.get_or_create_esi(id=type_id)
        return eve_type
    except Exception:
        logger.warning("Could not resolve EveType %s for sell order", type_id)
        return None


@transaction.atomic
def sync_sold_order_ledger_entries() -> dict[str, int]:
    """Upsert sold_order rows from corp wallet market sell transactions."""
    txs = [
        tx
        for tx in fetch_wallet_transactions()
        if tx.get("is_buy") is not True
    ]
    client_ids = {
        int(tx["client_id"]) for tx in txs if tx.get("client_id") is not None
    }
    counterparties = resolve_counterparties(client_ids)

    created = 0
    scanned = 0
    for tx in txs:
        type_id = tx.get("type_id")
        quantity = int(tx.get("quantity") or 0)
        transaction_id = tx.get("transaction_id")
        if type_id is None or quantity <= 0 or transaction_id is None:
            continue
        scanned += 1
        eve_type = _ensure_type(int(type_id))
        if eve_type is None:
            continue
        unit_price = tx.get("unit_price")
        unit_dec = Decimal(str(unit_price)) if unit_price is not None else None
        isk_total = unit_dec * quantity if unit_dec is not None else None
        occurred_at = _as_datetime(tx.get("date")) or timezone.now()
        client_id = tx.get("client_id")
        party = (
            counterparties.get(int(client_id))
            if client_id is not None
            else None
        )
        _, was_created = BuybackLedgerEntry.objects.update_or_create(
            reason=BuybackLedgerEntry.Reason.SOLD_ORDER,
            source_id=str(transaction_id),
            eve_type=eve_type,
            defaults={
                "quantity": quantity,
                "occurred_at": occurred_at,
                "unit_price": unit_dec,
                "isk_total": isk_total,
                "location_id": tx.get("location_id"),
                "counterparty_id": party.id if party else client_id,
                "counterparty_name": party.name if party else "",
                "counterparty_kind": party.kind if party else "",
            },
        )
        if was_created:
            created += 1
    return {"scanned": scanned, "created": created}
