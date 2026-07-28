"""Industry helpers for notification audiences, coordinators, and job matching."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from eveonline.models import EveCharacter, EveCharacterIndustryJob
from industry.helpers.producers import (
    PRODUCTION_ACTIVITIES,
    _blueprint_activity_pairs_for_product_type,
)
from industry.models import (
    IndustryOrder,
    IndustryOrderBlueprintCoordinator,
    IndustryOrderItemAssignment,
    IndustryOrderMineralCoordinator,
    IndustryOrderPiCoordinator,
)
from notifications.audiences import topic_subscribers, union_audiences
from notifications.service import notify_user, notify_users
from notifications.types.industry import (
    ORDER_ASSIGNMENT,
    ORDER_CREATED,
    ORDER_JOB,
)

logger = logging.getLogger(__name__)
User = get_user_model()

DEFAULT_PARTICIPATION_DAYS = 30


def users_participated_in_orders_since(since=None) -> set[int]:
    """
    User IDs who owned, were assigned to, or coordinated an order
    created (or coordinator volunteered) since `since`.
    """
    if since is None:
        since = timezone.now() - timedelta(days=DEFAULT_PARTICIPATION_DAYS)

    owner_char_ids = IndustryOrder.objects.filter(
        created_at__gte=since
    ).values_list("character_id", flat=True)

    assignee_char_ids = IndustryOrderItemAssignment.objects.filter(
        Q(order_item__order__created_at__gte=since)
        | Q(delivered_at__gte=since)
    ).values_list("character_id", flat=True)

    bp_coord = IndustryOrderBlueprintCoordinator.objects.filter(
        created_at__gte=since
    ).values_list("character_id", flat=True)
    min_coord = IndustryOrderMineralCoordinator.objects.filter(
        created_at__gte=since
    ).values_list("character_id", flat=True)
    pi_coord = IndustryOrderPiCoordinator.objects.filter(
        created_at__gte=since
    ).values_list("character_id", flat=True)

    character_pks = set(owner_char_ids) | set(assignee_char_ids)
    character_pks |= set(bp_coord) | set(min_coord) | set(pi_coord)

    return set(
        EveCharacter.objects.filter(pk__in=character_pks)
        .exclude(user_id__isnull=True)
        .values_list("user_id", flat=True)
    )


def new_order_audience(*, exclude_user_id: int | None = None) -> set[int]:
    participants = users_participated_in_orders_since()
    subscribers = topic_subscribers(ORDER_CREATED.key)
    audience = union_audiences(participants, subscribers)
    if exclude_user_id:
        audience.discard(exclude_user_id)
    return audience


def coordinators_for_order_item(order, item) -> list[dict]:
    """Structured coordinator list for assignment notification payloads."""
    out: list[dict] = []
    item_type_id = item.eve_type_id

    for coord in order.blueprint_coordinators.select_related(
        "character"
    ).prefetch_related("eve_types"):
        matching = [t for t in coord.eve_types.all() if t.id == item_type_id]
        if not matching:
            continue
        out.append(
            {
                "role": "blueprint",
                "character_id": coord.character.character_id,
                "character_name": coord.character.character_name,
                "eve_type_names": [t.name for t in matching],
            }
        )

    for coord in order.mineral_coordinators.select_related(
        "character"
    ).prefetch_related("eve_types"):
        out.append(
            {
                "role": "minerals",
                "character_id": coord.character.character_id,
                "character_name": coord.character.character_name,
                "eve_type_names": [t.name for t in coord.eve_types.all()],
            }
        )

    for coord in order.pi_coordinators.select_related(
        "character"
    ).prefetch_related("eve_types"):
        out.append(
            {
                "role": "PI",
                "character_id": coord.character.character_id,
                "character_name": coord.character.character_name,
                "eve_type_names": [t.name for t in coord.eve_types.all()],
            }
        )

    return out


def match_industry_job_to_assignment(
    job: EveCharacterIndustryJob,
) -> IndustryOrderItemAssignment | None:
    """
    Match a manufacturing/reaction job to an open undelivered assignment.

    Requires character (or same-user alts) + time overlap + blueprint produces
    the assignment line's product type.
    """
    if job.activity_id not in PRODUCTION_ACTIVITIES:
        return None

    character = job.character
    user_id = character.user_id
    if user_id:
        character_pks = list(
            EveCharacter.objects.filter(user_id=user_id).values_list(
                "pk", flat=True
            )
        )
    else:
        character_pks = [character.pk]

    assignments = (
        IndustryOrderItemAssignment.objects.filter(
            character_id__in=character_pks,
            delivered_at__isnull=True,
            order_item__order__fulfilled_at__isnull=True,
        )
        .select_related(
            "order_item", "order_item__order", "order_item__eve_type"
        )
        .order_by("id")
    )

    for assignment in assignments:
        order = assignment.order_item.order
        period_start = order.created_at
        period_end = order.order_period_end()
        if job.end_date < period_start or job.start_date > period_end:
            continue
        pairs = _blueprint_activity_pairs_for_product_type(
            assignment.order_item.eve_type_id
        )
        if (job.blueprint_type_id, job.activity_id) in pairs:
            return assignment
    return None


def emit_order_created(order: IndustryOrder, *, creator_user_id: int | None):
    items = list(order.items.select_related("eve_type").all())
    items_summary = ", ".join(
        f"{i.quantity}× {i.eve_type.name}" for i in items[:5]
    )
    if len(items) > 5:
        items_summary += f" (+{len(items) - 5} more)"
    location_name = ""
    if order.location_id:
        location_name = getattr(order.location, "location_name", "") or str(
            order.location_id
        )

    ctx = {
        "order_id": order.pk,
        "public_short_code": order.public_short_code,
        "needed_by": order.needed_by.isoformat() if order.needed_by else "",
        "items_summary": items_summary,
        "location_name": location_name,
    }
    audience_ids = new_order_audience(exclude_user_id=creator_user_id)
    users = User.objects.filter(id__in=audience_ids)
    notify_users(
        users,
        ORDER_CREATED.key,
        ctx,
        idempotency_key=f"industry.order.created:{order.pk}",
    )


def emit_order_assignment(assignment: IndustryOrderItemAssignment, user):
    item = assignment.order_item
    order = item.order
    ctx = {
        "order_id": order.pk,
        "public_short_code": order.public_short_code,
        "item_id": item.pk,
        "assignment_id": assignment.pk,
        "item_name": item.eve_type.name,
        "quantity": assignment.quantity,
        "coordinators": coordinators_for_order_item(order, item),
    }
    notify_user(
        user,
        ORDER_ASSIGNMENT.key,
        ctx,
        idempotency_key=(
            f"industry.order.assignment:{assignment.pk}:{assignment.quantity}"
        ),
    )


def emit_order_job_if_matched(job: EveCharacterIndustryJob) -> bool:
    assignment = match_industry_job_to_assignment(job)
    if not assignment:
        return False
    user = assignment.character.user
    if not user:
        return False
    item = assignment.order_item
    order = item.order
    ctx = {
        "order_id": order.pk,
        "public_short_code": order.public_short_code,
        "item_id": item.pk,
        "assignment_id": assignment.pk,
        "item_name": item.eve_type.name,
        "job_id": job.job_id,
    }
    notify_user(
        user,
        ORDER_JOB.key,
        ctx,
        idempotency_key=f"industry.order.job:{job.job_id}",
    )
    return True
