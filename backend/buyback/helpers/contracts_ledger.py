"""Sync buyback contract line items into the ledger (in + sold_contract)."""

from __future__ import annotations

import logging
from datetime import datetime

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from eveuniverse.models import EveType

from buyback.helpers.counterparty import resolve_counterparties
from buyback.models import (
    BUYBACK_CONTRACT_TYPE,
    BUYBACK_CORPORATION_ID,
    BuybackLedgerEntry,
)
from eveonline.client import EsiClient
from eveonline.helpers.corporations import (
    SCOPE_CORPORATION_CONTRACTS,
    get_director_with_scope,
)
from eveonline.models import EveCorporation, EveCorporationContract

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


def classify_contract_direction(
    contract: EveCorporationContract,
) -> str | None:
    """Return ledger reason for an M-EXC item_exchange, or None if irrelevant."""
    if contract.type != BUYBACK_CONTRACT_TYPE:
        return None
    if contract.assignee_id == BUYBACK_CORPORATION_ID:
        return BuybackLedgerEntry.Reason.IN_CONTRACT
    if (
        contract.issuer_corporation_id == BUYBACK_CORPORATION_ID
        and contract.assignee_id != BUYBACK_CORPORATION_ID
    ):
        return BuybackLedgerEntry.Reason.SOLD_CONTRACT
    return None


def contract_occurred_at(contract: EveCorporationContract) -> datetime:
    return (
        _as_datetime(contract.date_completed)
        or _as_datetime(contract.date_accepted)
        or _as_datetime(contract.date_issued)
        or timezone.now()
    )


def _in_or_out_q() -> Q:
    return Q(assignee_id=BUYBACK_CORPORATION_ID) | (
        Q(issuer_corporation_id=BUYBACK_CORPORATION_ID)
        & ~Q(assignee_id=BUYBACK_CORPORATION_ID)
    )


def _ensure_types(type_ids: set[int]) -> dict[int, EveType]:
    existing = {t.id: t for t in EveType.objects.filter(id__in=type_ids)}
    missing = type_ids - set(existing)
    for type_id in missing:
        try:
            eve_type, _ = EveType.objects.get_or_create_esi(id=type_id)
            existing[eve_type.id] = eve_type
        except Exception:
            logger.warning("Could not resolve EveType %s for ledger", type_id)
    return existing


def fetch_contract_items(contract_id: int) -> list[dict]:
    try:
        corp = EveCorporation.objects.get(
            corporation_id=BUYBACK_CORPORATION_ID
        )
    except EveCorporation.DoesNotExist:
        return []
    character = get_director_with_scope(corp, SCOPE_CORPORATION_CONTRACTS)
    if character is None:
        logger.warning("No director with corp contracts scope for M-EXC")
        return []
    response = EsiClient(character).get_corporation_contract_items(
        BUYBACK_CORPORATION_ID, contract_id
    )
    if not response.success():
        logger.warning(
            "Contract items ESI failed contract=%s code=%s",
            contract_id,
            response.response_code,
        )
        return []
    return list(response.results() or [])


def upsert_ledger_from_contract_items(
    *,
    contract: EveCorporationContract,
    reason: str,
    items: list[dict],
    counterparties: dict | None = None,
) -> int:
    """Persist included item lines as ledger rows. Returns created count."""
    occurred_at = contract_occurred_at(contract)
    if reason == BuybackLedgerEntry.Reason.IN_CONTRACT:
        counterparty_entity_id = contract.issuer_id
    else:
        counterparty_entity_id = contract.assignee_id

    if counterparties is None and counterparty_entity_id:
        counterparties = resolve_counterparties({int(counterparty_entity_id)})
    counterparties = counterparties or {}
    party = (
        counterparties.get(int(counterparty_entity_id))
        if counterparty_entity_id
        else None
    )

    included = [
        item
        for item in items
        if item.get("is_included", True) and int(item.get("quantity") or 0) > 0
    ]
    type_ids = {
        int(item["type_id"]) for item in included if item.get("type_id")
    }
    types_by_id = _ensure_types(type_ids)
    created = 0
    for item in included:
        type_id = int(item["type_id"])
        eve_type = types_by_id.get(type_id)
        if eve_type is None:
            continue
        record_id = item.get("record_id")
        source_id = (
            f"{contract.contract_id}:{record_id}"
            if record_id is not None
            else f"{contract.contract_id}:{type_id}:{item.get('quantity')}"
        )
        _, was_created = BuybackLedgerEntry.objects.update_or_create(
            reason=reason,
            source_id=str(source_id),
            eve_type=eve_type,
            defaults={
                "quantity": int(item["quantity"]),
                "occurred_at": occurred_at,
                "unit_price": None,
                "isk_total": None,
                "location_id": contract.start_location_id,
                "counterparty_id": (
                    party.id if party else counterparty_entity_id
                ),
                "counterparty_name": party.name if party else "",
                "counterparty_kind": party.kind if party else "",
            },
        )
        if was_created:
            created += 1
    return created


@transaction.atomic
def sync_contract_ledger_entries(
    *,
    contract_ids: list[int] | None = None,
    only_missing: bool = False,
) -> dict[str, int]:
    """
    Fetch ESI items for M-EXC in/out item_exchange contracts and upsert ledger.
    """
    qs = EveCorporationContract.objects.filter(
        corporation__corporation_id=BUYBACK_CORPORATION_ID,
        type=BUYBACK_CONTRACT_TYPE,
    ).filter(_in_or_out_q())
    if contract_ids is not None:
        qs = qs.filter(contract_id__in=contract_ids)

    contracts = list(qs)
    party_ids: set[int] = set()
    for contract in contracts:
        reason = classify_contract_direction(contract)
        if (
            reason == BuybackLedgerEntry.Reason.IN_CONTRACT
            and contract.issuer_id
        ):
            party_ids.add(int(contract.issuer_id))
        elif (
            reason == BuybackLedgerEntry.Reason.SOLD_CONTRACT
            and contract.assignee_id
        ):
            party_ids.add(int(contract.assignee_id))
    counterparties = resolve_counterparties(party_ids)

    scanned = 0
    created = 0
    skipped = 0
    for contract in contracts:
        reason = classify_contract_direction(contract)
        if reason is None:
            skipped += 1
            continue
        scanned += 1
        if only_missing:
            prefix = f"{contract.contract_id}:"
            if BuybackLedgerEntry.objects.filter(
                reason=reason, source_id__startswith=prefix
            ).exists():
                continue
        items = fetch_contract_items(contract.contract_id)
        created += upsert_ledger_from_contract_items(
            contract=contract,
            reason=reason,
            items=items,
            counterparties=counterparties,
        )

    return {
        "scanned": scanned,
        "created": created,
        "skipped": skipped,
    }


def backfill_contract_counterparties() -> dict[str, int]:
    """Fill counterparty fields on existing contract ledger rows from headers."""
    qs = EveCorporationContract.objects.filter(
        corporation__corporation_id=BUYBACK_CORPORATION_ID,
        type=BUYBACK_CONTRACT_TYPE,
    ).filter(_in_or_out_q())
    by_contract_id = {c.contract_id: c for c in qs}
    party_ids: set[int] = set()
    for contract in by_contract_id.values():
        reason = classify_contract_direction(contract)
        if (
            reason == BuybackLedgerEntry.Reason.IN_CONTRACT
            and contract.issuer_id
        ):
            party_ids.add(int(contract.issuer_id))
        elif (
            reason == BuybackLedgerEntry.Reason.SOLD_CONTRACT
            and contract.assignee_id
        ):
            party_ids.add(int(contract.assignee_id))
    counterparties = resolve_counterparties(party_ids)

    updated = 0
    for entry in BuybackLedgerEntry.objects.filter(
        reason__in=[
            BuybackLedgerEntry.Reason.IN_CONTRACT,
            BuybackLedgerEntry.Reason.SOLD_CONTRACT,
        ]
    ).iterator():
        try:
            contract_id = int(str(entry.source_id).split(":", 1)[0])
        except (TypeError, ValueError):
            continue
        contract = by_contract_id.get(contract_id)
        if contract is None:
            continue
        if entry.reason == BuybackLedgerEntry.Reason.IN_CONTRACT:
            entity_id = contract.issuer_id
        else:
            entity_id = contract.assignee_id
        if not entity_id:
            continue
        party = counterparties.get(int(entity_id))
        new_id = party.id if party else int(entity_id)
        new_name = party.name if party else str(entity_id)
        new_kind = party.kind if party else ""
        if (
            entry.counterparty_id == new_id
            and entry.counterparty_name == new_name
            and entry.counterparty_kind == new_kind
        ):
            continue
        entry.counterparty_id = new_id
        entry.counterparty_name = new_name
        entry.counterparty_kind = new_kind
        entry.save(
            update_fields=[
                "counterparty_id",
                "counterparty_name",
                "counterparty_kind",
            ]
        )
        updated += 1
    return {"updated": updated}
