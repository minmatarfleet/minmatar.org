"""Loose scored matching of ESI character contracts to industry orders."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime as dt_datetime, time as dt_time
from typing import Iterable

from django.db.models import Prefetch
from django.utils import timezone

from eveonline.client import EsiClient
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterContract,
    EveCorporation,
)
from market.helpers.contract_match import normalize_contract_items

from industry.models import (
    IndustryContractAssociation,
    IndustryOrder,
    IndustryOrderItemAssignment,
)

logger = logging.getLogger(__name__)

MATCH_THRESHOLD = 0.4

WEIGHT_ASSIGNEE_OWNER = 0.40
WEIGHT_ASSIGNEE_CONTRACT_TO = 0.20
WEIGHT_ISSUER_ASSIGNEE = 0.30
WEIGHT_TYPE_QTY = 0.30
WEIGHT_TYPE_QTY_OVER = 0.15
WEIGHT_LOCATION = 0.15
WEIGHT_SHORT_CODE = 0.15
WEIGHT_STATUS = 0.05
WEIGHT_TIME_WINDOW = 0.05


@dataclass(frozen=True)
class MatchCandidate:
    order: IndustryOrder
    assignment: IndustryOrderItemAssignment | None
    contract: EveCharacterContract
    score: float
    signals: dict


def order_period_bounds(order: IndustryOrder) -> tuple:
    """Return (period_start, period_end) aware datetimes for an order."""
    period_start = order.created_at
    if order.fulfilled_at is not None:
        period_end = order.fulfilled_at
    else:
        period_end = timezone.make_aware(
            dt_datetime.combine(order.needed_by, dt_time.max)
        )
    return period_start, period_end


def owner_entity_ids(character: EveCharacter) -> set[int]:
    ids: set[int] = set()
    if character.character_id:
        ids.add(int(character.character_id))
    if character.corporation_id:
        ids.add(int(character.corporation_id))
    if character.alliance_id:
        ids.add(int(character.alliance_id))
    return ids


def contract_to_name_matches(
    assignee_id: int | None, contract_to: str
) -> bool:
    """Weak fallback: resolve free-text contract_to against known entity names."""
    if not assignee_id or not (contract_to or "").strip():
        return False
    name = contract_to.strip()
    if EveCharacter.objects.filter(
        character_id=assignee_id, character_name__iexact=name
    ).exists():
        return True
    if EveCorporation.objects.filter(
        corporation_id=assignee_id, name__iexact=name
    ).exists():
        return True
    if EveAlliance.objects.filter(
        alliance_id=assignee_id, name__iexact=name
    ).exists():
        return True
    return False


def contract_in_order_window(
    contract: EveCharacterContract, period_start, period_end
) -> bool:
    """True if issued or completed time overlaps the order period."""
    for stamp in (contract.date_issued, contract.date_completed):
        if stamp is None:
            continue
        if period_start <= stamp <= period_end:
            return True
    # Outstanding contracts issued before the window but still open during it
    if (
        contract.date_issued is not None
        and contract.date_issued <= period_end
        and (
            contract.date_completed is None
            or contract.date_completed >= period_start
        )
        and contract.status in ("outstanding", "in_progress")
    ):
        return True
    return False


def aggregate_contract_items(raw_items: list[dict] | None) -> dict[int, int]:
    if not raw_items:
        return {}
    return normalize_contract_items(raw_items)


def fetch_character_contract_items(
    owner: EveCharacter, contract_id: int
) -> dict[int, int]:
    """Fetch and aggregate ESI contract items for the order owner's token."""
    response = EsiClient(owner).get_character_contract_items(contract_id)
    if not response.success():
        logger.debug(
            "Could not fetch items for contract %s (owner %s): %s",
            contract_id,
            owner.character_id,
            response.response_code,
        )
        return {}
    return aggregate_contract_items(response.results() or [])


def score_contract_for_assignment(
    *,
    order: IndustryOrder,
    assignment: IndustryOrderItemAssignment,
    contract: EveCharacterContract,
    owner_ids: set[int],
    item_quantities: dict[int, int] | None,
) -> MatchCandidate | None:
    signals: dict = {}
    score = 0.0

    assignee_id = contract.assignee_id
    if assignee_id and int(assignee_id) in owner_ids:
        score += WEIGHT_ASSIGNEE_OWNER
        signals["assignee_owner"] = True
    elif contract_to_name_matches(assignee_id, order.contract_to):
        score += WEIGHT_ASSIGNEE_CONTRACT_TO
        signals["assignee_contract_to"] = True
    else:
        return None

    score += WEIGHT_TIME_WINDOW
    signals["time_window"] = True

    issuer_id = contract.issuer_id
    if issuer_id and int(issuer_id) == int(assignment.character.character_id):
        score += WEIGHT_ISSUER_ASSIGNEE
        signals["issuer_assignee"] = True

    type_id = assignment.order_item.eve_type_id
    qty = assignment.quantity
    if item_quantities is not None and type_id in item_quantities:
        contract_qty = item_quantities[type_id]
        if 1 <= contract_qty <= qty:
            score += WEIGHT_TYPE_QTY
            signals["type_qty"] = contract_qty
        elif contract_qty > qty:
            score += WEIGHT_TYPE_QTY_OVER
            signals["type_qty_over"] = contract_qty

    location_id = order.location_id
    if location_id in (
        contract.start_location_id,
        contract.end_location_id,
    ):
        score += WEIGHT_LOCATION
        signals["location"] = True

    short_code = (order.public_short_code or "").strip()
    title = contract.title or ""
    if short_code and short_code.lower() in title.lower():
        score += WEIGHT_SHORT_CODE
        signals["short_code"] = True

    if contract.status in ("finished", "outstanding"):
        score += WEIGHT_STATUS
        signals["status"] = contract.status

    score = min(score, 1.0)
    if score < MATCH_THRESHOLD:
        return None

    return MatchCandidate(
        order=order,
        assignment=assignment,
        contract=contract,
        score=score,
        signals=signals,
    )


def score_contract_for_order(
    *,
    order: IndustryOrder,
    contract: EveCharacterContract,
    owner_ids: set[int],
) -> MatchCandidate | None:
    """Order-level association when assignee matches but no assignment pins."""
    signals: dict = {}
    score = 0.0

    assignee_id = contract.assignee_id
    if assignee_id and int(assignee_id) in owner_ids:
        score += WEIGHT_ASSIGNEE_OWNER
        signals["assignee_owner"] = True
    elif contract_to_name_matches(assignee_id, order.contract_to):
        score += WEIGHT_ASSIGNEE_CONTRACT_TO
        signals["assignee_contract_to"] = True
    else:
        return None

    score += WEIGHT_TIME_WINDOW
    signals["time_window"] = True

    location_id = order.location_id
    if location_id in (
        contract.start_location_id,
        contract.end_location_id,
    ):
        score += WEIGHT_LOCATION
        signals["location"] = True

    short_code = (order.public_short_code or "").strip()
    title = contract.title or ""
    if short_code and short_code.lower() in title.lower():
        score += WEIGHT_SHORT_CODE
        signals["short_code"] = True

    if contract.status in ("finished", "outstanding"):
        score += WEIGHT_STATUS
        signals["status"] = contract.status

    score = min(score, 1.0)
    if score < MATCH_THRESHOLD:
        return None

    return MatchCandidate(
        order=order,
        assignment=None,
        contract=contract,
        score=score,
        signals=signals,
    )


def candidate_contracts_for_order(
    order: IndustryOrder,
) -> list[EveCharacterContract]:
    owner = order.character
    period_start, period_end = order_period_bounds(order)
    owner_ids = owner_entity_ids(owner)

    qs = EveCharacterContract.objects.filter(
        character=owner,
        type="item_exchange",
    )
    contracts = []
    for contract in qs:
        if not contract_in_order_window(contract, period_start, period_end):
            continue
        assignee_id = contract.assignee_id
        if assignee_id and int(assignee_id) in owner_ids:
            contracts.append(contract)
            continue
        if contract_to_name_matches(assignee_id, order.contract_to):
            contracts.append(contract)
    return contracts


def match_order_contracts(
    order: IndustryOrder,
    *,
    item_quantities_by_contract: dict[int, dict[int, int]] | None = None,
    fetch_items: bool = True,
) -> list[MatchCandidate]:
    """
    Score contracts synced for the order owner against assignments.

    Prefer assignment-level matches. If a contract matches the order assignee
    filter but no assignment scores above threshold, keep an order-level row.
    """
    owner = order.character
    owner_ids = owner_entity_ids(owner)
    contracts = candidate_contracts_for_order(order)
    if not contracts:
        return []

    assignments = list(
        IndustryOrderItemAssignment.objects.filter(
            order_item__order=order
        ).select_related("character", "order_item")
    )

    items_cache = dict(item_quantities_by_contract or {})
    results: list[MatchCandidate] = []

    for contract in contracts:
        contract_id = int(contract.contract_id)
        if contract_id not in items_cache and fetch_items:
            items_cache[contract_id] = fetch_character_contract_items(
                owner, contract_id
            )
        item_quantities = items_cache.get(contract_id)

        assignment_matches: list[MatchCandidate] = []
        for assignment in assignments:
            candidate = score_contract_for_assignment(
                order=order,
                assignment=assignment,
                contract=contract,
                owner_ids=owner_ids,
                item_quantities=item_quantities,
            )
            if candidate is not None:
                assignment_matches.append(candidate)

        if assignment_matches:
            results.extend(assignment_matches)
            continue

        order_match = score_contract_for_order(
            order=order,
            contract=contract,
            owner_ids=owner_ids,
        )
        if order_match is not None:
            results.append(order_match)

    return results


def upsert_associations(candidates: Iterable[MatchCandidate]) -> int:
    """Create or update association rows; returns number of rows written."""
    written = 0
    for candidate in candidates:
        shared = {
            "score": candidate.score,
            "signals": candidate.signals,
            "contract_status": candidate.contract.status or "",
        }
        if candidate.assignment is not None:
            IndustryContractAssociation.objects.update_or_create(
                assignment=candidate.assignment,
                contract_id=candidate.contract.contract_id,
                defaults={**shared, "order": candidate.order},
            )
        else:
            IndustryContractAssociation.objects.update_or_create(
                order=candidate.order,
                contract_id=candidate.contract.contract_id,
                assignment=None,
                defaults=shared,
            )
        written += 1
    return written


def prune_stale_associations(
    order: IndustryOrder, keep: Iterable[MatchCandidate]
) -> int:
    """Delete associations for this order not present in the latest match set."""
    keep_keys = set()
    for candidate in keep:
        if candidate.assignment is not None:
            keep_keys.add(
                (
                    "a",
                    candidate.assignment.pk,
                    candidate.contract.contract_id,
                )
            )
        else:
            keep_keys.add(
                ("o", candidate.order.pk, candidate.contract.contract_id)
            )

    deleted = 0
    for assoc in IndustryContractAssociation.objects.filter(order=order):
        if assoc.assignment_id:
            key = ("a", assoc.assignment_id, assoc.contract_id)
        else:
            key = ("o", assoc.order_id, assoc.contract_id)
        if key not in keep_keys:
            assoc.delete()
            deleted += 1
    return deleted


def reconcile_order_contract_associations(
    order: IndustryOrder,
    *,
    fetch_items: bool = True,
    item_quantities_by_contract: dict[int, dict[int, int]] | None = None,
) -> int:
    """Match and upsert associations for one order; prune stale rows."""
    candidates = match_order_contracts(
        order,
        fetch_items=fetch_items,
        item_quantities_by_contract=item_quantities_by_contract,
    )
    written = upsert_associations(candidates)
    pruned = prune_stale_associations(order, candidates)
    logger.info(
        "Reconciled contract associations for order %s: wrote=%s pruned=%s",
        order.pk,
        written,
        pruned,
    )
    return written


def open_orders_queryset():
    """Unfulfilled industry orders with owner and assignments prefetched."""
    return (
        IndustryOrder.objects.filter(fulfilled_at__isnull=True)
        .select_related("character", "location")
        .prefetch_related(
            Prefetch(
                "items__assignments",
                queryset=IndustryOrderItemAssignment.objects.select_related(
                    "character", "order_item"
                ),
            )
        )
    )


def reconcile_open_order_contract_associations(
    *,
    fetch_items: bool = True,
) -> int:
    """Reconcile associations for all open industry orders."""
    total = 0
    for order in open_orders_queryset():
        total += reconcile_order_contract_associations(
            order, fetch_items=fetch_items
        )
    return total


def reconcile_associations_for_character(
    character_id: int,
    *,
    fetch_items: bool = True,
) -> int:
    """
    Reconcile open orders owned by the given ESI character_id
    (after their contracts were refreshed).
    """
    total = 0
    orders = open_orders_queryset().filter(
        character__character_id=character_id
    )
    for order in orders:
        total += reconcile_order_contract_associations(
            order, fetch_items=fetch_items
        )
    return total
