"""Credit/debit helpers for industry LP accounts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.db.models import Sum

from industry.models import (
    IndustryLoyaltyPointAccount,
    IndustryLoyaltyPointLedgerEntry,
)


class LpLedgerError(ValueError):
    """Invalid LP ledger post."""


def account_balance(account: IndustryLoyaltyPointAccount) -> int:
    """Current LP balance for an account (sum of ledger amounts)."""
    total = account.ledger_entries.aggregate(total=Sum("amount"))["total"]
    return int(total or 0)


def resolve_offer_isk_per_lp(account: IndustryLoyaltyPointAccount) -> int:
    """
    Current offer ISK/LP for a holder.

    Prefers account.isk_per_lp; falls back to the currency default.
    """
    if account.isk_per_lp is not None and account.isk_per_lp > 0:
        return int(account.isk_per_lp)
    return int(account.loyalty_point.default_isk_per_lp)


@dataclass(frozen=True)
class RemainingLot:
    """Remaining quantity at a single intake price after FIFO consumption."""

    isk_per_lp: int
    quantity: int


def remaining_lots(account: IndustryLoyaltyPointAccount) -> list[RemainingLot]:
    """
    FIFO remaining inventory by lot price.

    Walks credits then consumes them with later debits in chronological order.
    """
    lots: list[list[int]] = []  # [isk_per_lp, remaining_qty]
    entries = account.ledger_entries.order_by("created_at", "id").values_list(
        "amount", "isk_per_lp"
    )
    for amount, isk_per_lp in entries:
        if amount > 0:
            lots.append([int(isk_per_lp), int(amount)])
            continue
        need = -int(amount)
        while need > 0 and lots:
            price, qty = lots[0]
            take = min(qty, need)
            qty -= take
            need -= take
            if qty == 0:
                lots.pop(0)
            else:
                lots[0][1] = qty
        if need > 0:
            # Should not happen if posts enforce no overdraft; ignore remainder.
            break
    return [
        RemainingLot(isk_per_lp=price, quantity=qty)
        for price, qty in lots
        if qty > 0
    ]


def weighted_average_cost_isk_per_lp(
    account: IndustryLoyaltyPointAccount,
) -> Optional[float]:
    """Weighted average ISK/LP of remaining FIFO lots, or None if empty."""
    lots = remaining_lots(account)
    if not lots:
        return None
    total_qty = sum(lot.quantity for lot in lots)
    if total_qty <= 0:
        return None
    cost = sum(lot.quantity * lot.isk_per_lp for lot in lots)
    return cost / total_qty


@transaction.atomic
def post_ledger_entry(
    account: IndustryLoyaltyPointAccount,
    amount: int,
    isk_per_lp: int,
    *,
    notes: str = "",
    user=None,
) -> IndustryLoyaltyPointLedgerEntry:
    """
    Append a credit/debit lot and return the new entry.

    ``isk_per_lp`` is required (lot price). Rejects zero amounts, non-positive
    prices, and debits that would overdraw the account.
    """
    amount = int(amount)
    isk_per_lp = int(isk_per_lp)
    if amount == 0:
        raise LpLedgerError("Ledger amount must be non-zero.")
    if isk_per_lp <= 0:
        raise LpLedgerError("isk_per_lp must be a positive integer.")

    locked = IndustryLoyaltyPointAccount.objects.select_for_update().get(
        pk=account.pk
    )
    balance = account_balance(locked)
    if amount < 0 and balance + amount < 0:
        raise LpLedgerError(
            f"Insufficient LP balance: have {balance}, debit {-amount}."
        )
    balance_after = balance + amount
    return IndustryLoyaltyPointLedgerEntry.objects.create(
        account=locked,
        amount=amount,
        isk_per_lp=isk_per_lp,
        notes=notes or "",
        balance_after=balance_after,
        created_by=user,
    )
