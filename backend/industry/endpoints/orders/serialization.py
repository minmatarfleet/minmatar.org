"""Map industry order models to API response models."""

from decimal import Decimal

from industry.endpoints.orders.schemas import (
    AssignmentResponse,
    OrderItemResponse,
)
from industry.helpers.order_assignments import self_assign_window_ends_at


def first_list_item_targets_from_assignments(assignments):
    """First non-null target price / margin on assignments (fallback for list tooltips)."""
    unit: Decimal | None = None
    margin: Decimal | None = None
    for a in assignments:
        if unit is None and a.target_unit_price is not None:
            unit = a.target_unit_price
        if margin is None and a.target_estimated_margin is not None:
            margin = a.target_estimated_margin
        if unit is not None and margin is not None:
            break
    return unit, margin


def order_line_list_targets(item):
    """
    Target price/margin for list API: order item row first, then any assignment.
    """
    unit = item.target_unit_price
    margin = item.target_estimated_margin
    if unit is None or margin is None:
        a_unit, a_margin = first_list_item_targets_from_assignments(
            item.assignments.all()
        )
        if unit is None:
            unit = a_unit
        if margin is None:
            margin = a_margin
    return unit, margin


def assignment_to_response(assignment) -> AssignmentResponse:
    return AssignmentResponse(
        id=assignment.pk,
        character_id=assignment.character.character_id,
        character_name=assignment.character.character_name,
        quantity=assignment.quantity,
        target_unit_price=assignment.target_unit_price,
        target_estimated_margin=assignment.target_estimated_margin,
        delivered_at=assignment.delivered_at,
    )


def order_item_to_response(order, item) -> OrderItemResponse:
    assignments = list(item.assignments.all())
    assigned_sum = sum(a.quantity for a in assignments)
    unassigned = max(0, item.quantity - assigned_sum)
    return OrderItemResponse(
        id=item.pk,
        eve_type_id=item.eve_type_id,
        eve_type_name=item.eve_type.name,
        quantity=item.quantity,
        unassigned_quantity=unassigned,
        self_assign_maximum=item.self_assign_maximum,
        self_assign_window_ends_at=self_assign_window_ends_at(order),
        target_unit_price=item.target_unit_price,
        target_estimated_margin=item.target_estimated_margin,
        assignments=[assignment_to_response(a) for a in assignments],
    )
