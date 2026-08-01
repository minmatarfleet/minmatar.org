"""Manufacturer leaderboard: delivered ISK estimate over a rolling window."""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models.functions import Coalesce
from django.utils import timezone

from eveonline.models import EvePlayer
from industry.models import IndustryOrderItemAssignment
from tribes.constants import MANUFACTURING_PRODUCTION_GROUP_CODES
from tribes.models import TribeGroupMembership

LEADERBOARD_WINDOW = timedelta(days=30)


def assignment_unit_price(assignment: IndustryOrderItemAssignment) -> Decimal:
    return Decimal(
        assignment.target_unit_price
        or assignment.order_item.target_unit_price
        or 0
    )


def assignment_delivery_at(assignment: IndustryOrderItemAssignment):
    return assignment.delivered_at or assignment.order_item.order.fulfilled_at


def eligible_manufacturing_production_user_ids() -> set[int]:
    return set(
        TribeGroupMembership.objects.filter(
            status=TribeGroupMembership.STATUS_ACTIVE,
            tribe_group__code__in=MANUFACTURING_PRODUCTION_GROUP_CODES,
        ).values_list("user_id", flat=True)
    )


def build_orders_character_statistics() -> list[dict]:
    """
    Rank eligible manufacturing-production members by delivered ISK estimate
    (qty × target unit price) in the last 30 days.
    """
    eligible_user_ids = eligible_manufacturing_production_user_ids()
    if not eligible_user_ids:
        return []

    since = timezone.now() - LEADERBOARD_WINDOW
    assignments = (
        IndustryOrderItemAssignment.objects.annotate(
            delivery_at=Coalesce(
                "delivered_at",
                "order_item__order__fulfilled_at",
            )
        )
        .filter(
            delivery_at__gte=since,
            character__user_id__in=eligible_user_ids,
        )
        .select_related("character", "order_item")
    )

    totals: dict[int, Decimal] = defaultdict(Decimal)
    for assignment in assignments:
        user_id = assignment.character.user_id
        if not user_id:
            continue
        amount = Decimal(assignment.quantity) * assignment_unit_price(
            assignment
        )
        if amount > 0:
            totals[user_id] += amount

    if not totals:
        return []

    players = EvePlayer.objects.filter(
        user_id__in=totals.keys()
    ).select_related("primary_character")
    primary_by_user = {
        player.user_id: (
            player.primary_character.character_id,
            player.primary_character.character_name or None,
        )
        for player in players
        if player.primary_character_id
    }

    result = []
    for user_id, amount in totals.items():
        char_id, char_name = primary_by_user.get(user_id, (None, None))
        result.append(
            {
                "primary_character_id": char_id,
                "primary_character_name": char_name,
                "delivered_isk_estimate": amount,
            }
        )

    result.sort(
        key=lambda row: (
            -row["delivered_isk_estimate"],
            (row["primary_character_name"] or "").lower(),
        )
    )
    return result
