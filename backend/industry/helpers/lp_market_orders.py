"""Service for LP buyback market orders (create / claim / transition / Discord)."""

from __future__ import annotations

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from industry.helpers.lp_ledger import (
    LpLedgerError,
    post_sell_order_completion_ledger,
)
from industry.models import (
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointMarketOrder,
    IndustryLoyaltyPointMarketOrderClaim,
)

OPEN = IndustryLoyaltyPointMarketOrder.Status.OPEN
CLAIMED = IndustryLoyaltyPointMarketOrder.Status.CLAIMED
AWAITING_LP = IndustryLoyaltyPointMarketOrder.Status.AWAITING_LP
AWAITING_ISK = IndustryLoyaltyPointMarketOrder.Status.AWAITING_ISK
COMPLETED = IndustryLoyaltyPointMarketOrder.Status.COMPLETED
CANCELLED = IndustryLoyaltyPointMarketOrder.Status.CANCELLED

ACTIVE_STATUSES = (OPEN, CLAIMED, AWAITING_LP, AWAITING_ISK)

# Maximum LP quantity for sell orders; buy orders have no quantity cap.
MAX_SELL_LP = 2_500_000

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    OPEN: frozenset({CLAIMED, CANCELLED}),
    CLAIMED: frozenset({AWAITING_LP, CANCELLED}),
    AWAITING_LP: frozenset({AWAITING_ISK, CANCELLED}),
    AWAITING_ISK: frozenset({COMPLETED, CANCELLED}),
}


class LpMarketOrderError(ValueError):
    """Invalid LP market order mutation."""


def format_lp_quantity(quantity: int) -> str:
    """Human LP amount for titles (e.g. 2.5M, 850K)."""
    qty = int(quantity)
    if qty >= 1_000_000:
        value = qty / 1_000_000
        text = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{text}M"
    if qty >= 1_000:
        value = qty / 1_000
        text = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{text}K"
    return f"{qty:,}"


def currency_short_name(name: str) -> str:
    mapping = {
        "Tribal Liberation Force": "TLIB",
        "24th Imperial Crusade": "24th",
        "State Protectorate": "State",
        "Federal Defense Union": "FDU",
    }
    return mapping.get(name, name[:12])


def create_order(
    *,
    currency: IndustryLoyaltyPoint,
    side: str,
    quantity: int,
    isk_per_lp: int,
    created_by,
    notes: str = "",
    destination_character_name: str = "",
) -> IndustryLoyaltyPointMarketOrder:
    quantity = int(quantity)
    if quantity <= 0:
        raise LpMarketOrderError("quantity must be a positive integer.")
    if (
        side == IndustryLoyaltyPointMarketOrder.Side.SELL
        and quantity > MAX_SELL_LP
    ):
        raise LpMarketOrderError(
            f"Sell orders cannot exceed {MAX_SELL_LP:,} LP."
        )

    destination = (destination_character_name or "").strip()
    if side == IndustryLoyaltyPointMarketOrder.Side.BUY and not destination:
        raise LpMarketOrderError(
            "destination_character_name is required for buy orders."
        )

    order = IndustryLoyaltyPointMarketOrder.objects.create(
        loyalty_point=currency,
        side=side,
        quantity=quantity,
        isk_per_lp=isk_per_lp,
        status=OPEN,
        created_by=created_by,
        destination_character_name=destination,
        notes=notes,
    )
    order.loyalty_point = currency
    order.created_by = created_by
    # Circular with lp_buyback_discord (format helpers live here).
    # pylint: disable=import-outside-toplevel
    from industry.helpers import lp_buyback_discord

    lp_buyback_discord.notify_order_created(order)
    return order


def claimed_quantity(order: IndustryLoyaltyPointMarketOrder) -> int:
    """Sum of claim amounts for an order (uses prefetch cache when present)."""
    cache = getattr(order, "_prefetched_objects_cache", None)
    if cache is not None and "claims" in cache:
        return int(sum(claim.amount for claim in order.claims.all()))
    total = order.claims.aggregate(total=Sum("amount"))["total"]
    return int(total or 0)


def remaining_quantity(order: IndustryLoyaltyPointMarketOrder) -> int:
    return max(0, int(order.quantity) - claimed_quantity(order))


def _resolve_claim_amount(amount: int | None, remaining: int) -> int:
    if amount is None:
        return remaining
    claim_amount = int(amount)
    if claim_amount <= 0:
        raise LpMarketOrderError("amount must be a positive integer.")
    if claim_amount > remaining:
        raise LpMarketOrderError(
            f"amount exceeds remaining unclaimed quantity ({remaining:,})."
        )
    return claim_amount


def _apply_sell_claim_destination(
    order: IndustryLoyaltyPointMarketOrder,
    dest_character: str,
    dest_corporation: str,
) -> None:
    """Copy sell-claim LP destination onto the order."""
    if order.side != IndustryLoyaltyPointMarketOrder.Side.SELL:
        return
    if dest_character:
        order.destination_character_name = dest_character
    elif dest_corporation and not order.destination_character_name:
        order.destination_character_name = dest_corporation


@transaction.atomic
def claim_order(
    order: IndustryLoyaltyPointMarketOrder,
    user,
    *,
    amount: int | None = None,
    destination_character_name: str = "",
    destination_corporation_name: str = "",
) -> IndustryLoyaltyPointMarketOrder:
    locked = (
        IndustryLoyaltyPointMarketOrder.objects.select_for_update()
        .select_related("loyalty_point", "created_by", "claimed_by")
        .get(pk=order.pk)
    )
    if locked.status != OPEN:
        raise LpMarketOrderError("Only open orders can be claimed.")

    already_claimed = claimed_quantity(locked)
    remaining = int(locked.quantity) - already_claimed
    if remaining <= 0:
        raise LpMarketOrderError("Order is already fully claimed.")

    claim_amount = _resolve_claim_amount(amount, remaining)
    dest_character = (destination_character_name or "").strip()
    dest_corporation = (destination_corporation_name or "").strip()
    if not dest_character and not dest_corporation:
        raise LpMarketOrderError(
            "destination is required when claiming an order."
        )

    claim = IndustryLoyaltyPointMarketOrderClaim.objects.create(
        order=locked,
        amount=claim_amount,
        destination_character_name=dest_character,
        destination_corporation_name=dest_corporation,
        claimed_by=user,
    )

    if locked.claimed_by_id is None:
        locked.claimed_by = user

    # Sell claims set LP destination on the order. Buy claims store ISK
    # payout on the claim only — order.destination is already the LP dest.
    _apply_sell_claim_destination(locked, dest_character, dest_corporation)

    fully_claimed = already_claimed + claim_amount >= int(locked.quantity)
    if fully_claimed:
        locked.status = (
            AWAITING_LP if locked.destination_character_name else CLAIMED
        )
    locked.save()

    # pylint: disable=import-outside-toplevel
    from industry.helpers import lp_buyback_discord

    if locked.status == AWAITING_LP:
        lp_buyback_discord.notify_order_status_changed(locked)
    else:
        lp_buyback_discord.notify_order_claimed(locked, claim=claim)
    return locked


@transaction.atomic
def transition_order(
    order: IndustryLoyaltyPointMarketOrder,
    new_status: str,
    *,
    destination_character_name: str | None = None,
) -> IndustryLoyaltyPointMarketOrder:
    locked = (
        IndustryLoyaltyPointMarketOrder.objects.select_for_update()
        .select_related("loyalty_point", "created_by", "claimed_by")
        .get(pk=order.pk)
    )
    if new_status == locked.status:
        return locked

    allowed = ALLOWED_TRANSITIONS.get(locked.status, frozenset())
    if new_status not in allowed:
        raise LpMarketOrderError(
            f"Cannot transition from {locked.status} to {new_status}."
        )

    if new_status == AWAITING_LP:
        dest = (
            destination_character_name
            if destination_character_name is not None
            else locked.destination_character_name
        )
        if not dest or not str(dest).strip():
            raise LpMarketOrderError(
                "destination_character_name is required when awaiting LP."
            )
        locked.destination_character_name = str(dest).strip()
    elif destination_character_name is not None:
        locked.destination_character_name = str(
            destination_character_name
        ).strip()

    previous = locked.status
    locked.status = new_status
    if new_status == COMPLETED:
        locked.completed_at = timezone.now()
        if locked.side == IndustryLoyaltyPointMarketOrder.Side.SELL:
            try:
                post_sell_order_completion_ledger(locked)
            except LpLedgerError as exc:
                raise LpMarketOrderError(str(exc)) from exc
    locked.save()

    if previous != locked.status:
        # pylint: disable=import-outside-toplevel
        from industry.helpers import lp_buyback_discord

        lp_buyback_discord.notify_order_status_changed(locked)
    return locked


def update_order_notes(
    order: IndustryLoyaltyPointMarketOrder, notes: str
) -> IndustryLoyaltyPointMarketOrder:
    order.notes = notes.strip()
    order.save(update_fields=["notes", "updated_at"])
    return order


def update_destination(
    order: IndustryLoyaltyPointMarketOrder, destination_character_name: str
) -> IndustryLoyaltyPointMarketOrder:
    order.destination_character_name = destination_character_name.strip()
    order.save(update_fields=["destination_character_name", "updated_at"])
    return order


ACTION_LP_SENT = "lp_sent"
ACTION_ISK_SENT = "isk_sent"


def expected_ack_user(order: IndustryLoyaltyPointMarketOrder, action: str):
    # pylint: disable=import-outside-toplevel
    from industry.helpers.lp_buyback_discord import isk_payer, lp_sender

    if action == ACTION_LP_SENT:
        return lp_sender(order)
    if action == ACTION_ISK_SENT:
        return isk_payer(order)
    raise LpMarketOrderError(f"Unknown ack action: {action}")


def discord_ack_order(
    order: IndustryLoyaltyPointMarketOrder,
    *,
    action: str,
) -> IndustryLoyaltyPointMarketOrder:
    action = (action or "").strip().lower()
    if action == ACTION_LP_SENT:
        if order.status != AWAITING_LP:
            raise LpMarketOrderError(
                f"Cannot ack LP sent while status is {order.status}."
            )
        return transition_order(order, AWAITING_ISK)
    if action == ACTION_ISK_SENT:
        if order.status != AWAITING_ISK:
            raise LpMarketOrderError(
                f"Cannot ack ISK sent while status is {order.status}."
            )
        return transition_order(order, COMPLETED)
    raise LpMarketOrderError(f"Unknown ack action: {action}")
