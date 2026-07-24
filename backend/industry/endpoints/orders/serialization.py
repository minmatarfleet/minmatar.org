"""Map industry order models to API response models."""

from decimal import Decimal

from industry.endpoints.orders.schemas import (
    AssignmentResponse,
    BlueprintCoordinatorEveTypeResponse,
    BlueprintCoordinatorResponse,
    OrderItemResponse,
    OrderLpStockpileContactResponse,
    OrderLpStockpileResponse,
)
from industry.helpers.order_assignments import self_assign_window_ends_at
from industry.helpers.order_lp_stockpiles import (
    OrderLpStockpile,
    resolve_order_lp_stockpiles,
)


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
        has_blueprints=assignment.has_blueprints,
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


def lp_stockpile_to_response(
    row: OrderLpStockpile,
) -> OrderLpStockpileResponse:
    return OrderLpStockpileResponse(
        account_id=row.account_id,
        account_name=row.account_name,
        loyalty_point_id=row.loyalty_point_id,
        loyalty_point_name=row.loyalty_point_name,
        corporation_id=row.corporation_id,
        balance=row.balance,
        contacts=[
            OrderLpStockpileContactResponse(
                character_name=c.character_name,
                discord_user_id=c.discord_user_id,
                discord_username=c.discord_username,
            )
            for c in row.contacts
        ],
        character_id=row.character_id,
        account_corporation_id=row.account_corporation_id,
    )


def blueprint_coordinator_to_response(
    coordinator,
) -> BlueprintCoordinatorResponse:
    eve_types = sorted(coordinator.eve_types.all(), key=lambda t: t.name or "")
    return BlueprintCoordinatorResponse(
        id=coordinator.pk,
        character_id=coordinator.character.character_id,
        character_name=coordinator.character.character_name,
        eve_types=[
            BlueprintCoordinatorEveTypeResponse(
                eve_type_id=t.id,
                eve_type_name=t.name,
            )
            for t in eve_types
        ],
    )


def order_lp_stockpiles_response(order) -> list[OrderLpStockpileResponse]:
    return [
        lp_stockpile_to_response(row)
        for row in resolve_order_lp_stockpiles(order)
    ]


def order_blueprint_coordinators_response(
    order,
) -> list[BlueprintCoordinatorResponse]:
    return [
        blueprint_coordinator_to_response(c)
        for c in order.blueprint_coordinators.all()
    ]


def order_mineral_coordinators_response(
    order,
) -> list[BlueprintCoordinatorResponse]:
    return [
        blueprint_coordinator_to_response(c)
        for c in order.mineral_coordinators.all()
    ]


def order_pi_coordinators_response(
    order,
) -> list[BlueprintCoordinatorResponse]:
    return [
        blueprint_coordinator_to_response(c)
        for c in order.pi_coordinators.all()
    ]


def coordinator_eve_types_response(
    eve_types,
) -> list[BlueprintCoordinatorEveTypeResponse]:
    return [
        BlueprintCoordinatorEveTypeResponse(
            eve_type_id=t.id,
            eve_type_name=t.name,
        )
        for t in eve_types
    ]
