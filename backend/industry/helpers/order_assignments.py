"""Rules for creating industry order line assignments (availability + 48h self-assign cap)."""

from datetime import timedelta

from django.utils import timezone

SELF_ASSIGN_WINDOW = timedelta(hours=48)


def self_assign_window_ends_at(order):
    """UTC-aware datetime when the early per-character cap no longer applies."""
    return order.created_at + SELF_ASSIGN_WINDOW


def within_self_assign_window(order) -> bool:
    return timezone.now() < self_assign_window_ends_at(order)


def validate_assignment_quantity(
    *,
    line_quantity: int,
    self_assign_maximum: int | None,
    total_assigned: int,
    quantity_for_character: int,
    add_quantity: int,
    order,
) -> str | None:
    """
    Return an error detail string if this assignment is not allowed, else None.
    `quantity_for_character` is current assigned total for this character on the line.
    """
    if add_quantity < 1:
        return "Quantity must be at least 1."
    remaining = max(line_quantity - total_assigned, 0)
    if add_quantity > remaining:
        return f"Only {remaining} unit(s) remain unassigned on this line."

    if within_self_assign_window(order) and self_assign_maximum is not None:
        cap = self_assign_maximum
        if quantity_for_character + add_quantity > cap:
            return (
                f"During the first 48 hours after the order was created, each character "
                f"may assign at most {cap} unit(s) on this line "
                f"(you already have {quantity_for_character})."
            )
    return None
