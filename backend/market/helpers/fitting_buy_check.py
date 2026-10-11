"""Run progressive Check Jita jobs and apply results to order items."""

from __future__ import annotations

import logging

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from eveuniverse.models import EveType

from market.helpers.fitting_buy_allocations import cached_jita_sell_mins
from market.helpers.fitting_buy_alternates import (
    listed_substitutes_by_preferred,
    shopping_alternate_types_for,
)
from market.helpers.fitting_buy_jita import (
    JitaSellDepth,
    jita_sell_depth_by_type_id,
)
from market.helpers.fitting_buy_plan import (
    build_shopping_plan,
    sync_order_items,
)
from market.models.fitting_buy_order import (
    FittingBuyJitaCheck,
    FittingBuyJitaCheckStatus,
    FittingBuyOrder,
    FittingBuyOrderItem,
)

logger = logging.getLogger(__name__)

CHECK_COOLDOWN_SECONDS = 30
CHECK_HOURLY_CAP = 10
CHECK_MAX_TYPES = 200
STALE_PENDING_SECONDS = 20
VARIANT_ALTERNATE_LIMIT = 20


class JitaThrottleError(RuntimeError):
    """User hit Check Jita cooldown or hourly cap."""


def throttle_key_cooldown(user_id: int) -> str:
    return f"market:fitting_buy_jita_cooldown:{user_id}"


def throttle_key_hourly(user_id: int) -> str:
    return f"market:fitting_buy_jita_hourly:{user_id}"


def check_user_throttle(user_id: int) -> str | None:
    if cache.get(throttle_key_cooldown(user_id)):
        return "Please wait before starting another Jita check."
    hourly = cache.get(throttle_key_hourly(user_id)) or 0
    if int(hourly) >= CHECK_HOURLY_CAP:
        return "Hourly Jita check limit reached. Try again later."
    return None


def mark_user_throttled(user_id: int) -> None:
    cache.set(throttle_key_cooldown(user_id), "1", CHECK_COOLDOWN_SECONDS)
    hourly_key = throttle_key_hourly(user_id)
    current = int(cache.get(hourly_key) or 0)
    cache.set(hourly_key, current + 1, 3600)


def apply_depth_to_order(
    order: FittingBuyOrder,
    depths: dict[int, JitaSellDepth],
    plan=None,
) -> None:
    if plan is None:
        plan = build_shopping_plan(order)
    now = timezone.now()
    items = {row.eve_type_id: row for row in order.items.all()}
    to_update: list[FittingBuyOrderItem] = []
    for type_id, buy_qty in plan.buy.items():
        if buy_qty <= 0:
            continue
        depth = depths.get(type_id)
        row = items.get(type_id)
        if row is None or depth is None:
            continue
        row.jita_sell_volume = depth.volume
        row.jita_order_count = depth.order_count
        row.jita_sell_min = depth.sell_min
        to_update.append(row)
    updated_ids = {row.eve_type_id for row in to_update}
    for row in items.values():
        if row.eve_type_id in updated_ids:
            continue
        if row.needed_qty > 0 or row.buy_qty <= 0:
            continue
        depth = depths.get(row.eve_type_id)
        if depth is None:
            continue
        row.jita_sell_volume = depth.volume
        row.jita_order_count = depth.order_count
        row.jita_sell_min = depth.sell_min
        to_update.append(row)

    with transaction.atomic():
        if to_update:
            FittingBuyOrderItem.objects.bulk_update(
                to_update,
                ["jita_sell_volume", "jita_order_count", "jita_sell_min"],
            )
        order.jita_checked_at = now
        order.save(update_fields=["jita_checked_at", "updated_at"])


def _depth_cache_entry(depth: JitaSellDepth) -> dict:
    return {
        "volume": depth.volume,
        "order_count": depth.order_count,
        "sell_min": (
            str(depth.sell_min) if depth.sell_min is not None else None
        ),
    }


def _short_variant_type_ids(
    *,
    plan,
    depths: dict[int, JitaSellDepth],
    already: set[int],
    remaining: int,
    listed_by_preferred: dict[int, set[int]] | None = None,
    jita_sell_min_by_type: dict | None = None,
) -> list[int]:
    if remaining <= 0:
        return []
    short_ids = []
    for tid, buy_qty in plan.buy.items():
        if buy_qty <= 0:
            continue
        depth = depths.get(tid)
        if depth is None:
            continue
        if buy_qty > depth.volume:
            short_ids.append(tid)
    if not short_ids:
        return []
    eve_types = list(EveType.objects.filter(id__in=short_ids))
    listed_map = listed_by_preferred or {}
    ids: list[int] = []
    seen = set(already)
    for eve_type in eve_types:
        listed = listed_map.get(eve_type.id, set())
        for alt in shopping_alternate_types_for(
            eve_type,
            limit=VARIANT_ALTERNATE_LIMIT,
            listed_substitute_ids=listed,
            jita_sell_min_by_type=jita_sell_min_by_type,
        ):
            if alt.id in seen:
                continue
            ids.append(alt.id)
            seen.add(alt.id)
            if len(ids) >= remaining:
                logger.warning(
                    "Truncating short-item variant Jita fetch at %s types",
                    CHECK_MAX_TYPES,
                )
                return ids
    return ids


def run_fitting_buy_jita_check(check_id: int) -> None:
    check = (
        FittingBuyJitaCheck.objects.select_related("order")
        .filter(pk=check_id)
        .first()
    )
    if check is None:
        return
    order = check.order
    check.status = FittingBuyJitaCheckStatus.RUNNING
    check.save(update_fields=["status", "updated_at"])

    try:
        plan = sync_order_items(order)
        type_ids = [tid for tid, qty in plan.buy.items() if qty > 0]
        if check.type_ids:
            requested = {int(t) for t in check.type_ids}
            type_ids = [t for t in type_ids if t in requested] or list(
                requested
            )
        if len(type_ids) > CHECK_MAX_TYPES:
            raise RuntimeError(
                f"Too many types to check ({len(type_ids)}; max {CHECK_MAX_TYPES})."
            )

        check.total_count = len(type_ids)
        check.done_count = 0
        check.type_ids = type_ids
        check.results = {}
        check.save(
            update_fields=[
                "total_count",
                "done_count",
                "type_ids",
                "results",
                "updated_at",
            ]
        )

        def on_progress(done, total, depth):
            results = dict(check.results or {})
            if depth is not None:
                results[str(depth.type_id)] = depth.to_dict()
            FittingBuyJitaCheck.objects.filter(pk=check.pk).update(
                done_count=done,
                total_count=total,
                results=results,
                updated_at=timezone.now(),
            )
            check.done_count = done
            check.total_count = total
            check.results = results

        depths = jita_sell_depth_by_type_id(
            type_ids,
            force_refresh=check.force_refresh,
            on_progress=on_progress,
        )
        remaining_slots = max(0, CHECK_MAX_TYPES - len(type_ids))
        listed_by_preferred = listed_substitutes_by_preferred(
            order.lines.values_list("fitting_id", flat=True)
        )
        prices = cached_jita_sell_mins(order)
        for tid, depth in depths.items():
            if depth.sell_min is not None:
                prices[tid] = depth.sell_min
        variant_ids = _short_variant_type_ids(
            plan=plan,
            depths=depths,
            already=set(type_ids),
            remaining=remaining_slots,
            listed_by_preferred=listed_by_preferred,
            jita_sell_min_by_type=prices,
        )
        variant_depths: dict[int, JitaSellDepth] = {}
        if variant_ids:
            buy_done = len(depths)
            combined_total = buy_done + len(variant_ids)
            check.type_ids = list(type_ids) + variant_ids
            check.total_count = combined_total
            check.save(update_fields=["type_ids", "total_count", "updated_at"])

            def on_variant_progress(
                done, total, depth
            ):  # pylint: disable=unused-argument
                on_progress(buy_done + done, combined_total, depth)

            variant_depths = jita_sell_depth_by_type_id(
                variant_ids,
                force_refresh=check.force_refresh,
                on_progress=on_variant_progress,
            )
            depths.update(variant_depths)

        apply_depth_to_order(order, depths, plan=plan)
        order.variant_jita_cache = {
            str(tid): _depth_cache_entry(depth)
            for tid, depth in variant_depths.items()
        }
        order.save(update_fields=["variant_jita_cache", "updated_at"])

        check.refresh_from_db()
        check.status = FittingBuyJitaCheckStatus.COMPLETE
        check.results = {str(k): v.to_dict() for k, v in depths.items()}
        check.done_count = check.total_count
        check.finished_at = timezone.now()
        check.error = ""
        check.save(
            update_fields=[
                "status",
                "results",
                "done_count",
                "finished_at",
                "error",
                "updated_at",
            ]
        )
    except Exception as exc:
        logger.exception("Fitting buy Jita check %s failed", check_id)
        check.status = FittingBuyJitaCheckStatus.FAILED
        check.error = str(exc)
        check.finished_at = timezone.now()
        check.save(
            update_fields=["status", "error", "finished_at", "updated_at"]
        )


def start_jita_check_async(check_id: int) -> None:
    def _enqueue():
        # Avoid circular import: tasks → fitting_buy_check → tasks
        # pylint: disable=import-outside-toplevel
        from market.tasks import run_fitting_buy_jita_check_task

        run_fitting_buy_jita_check_task.delay(check_id)

    transaction.on_commit(_enqueue)


def _is_stale_pending(check: FittingBuyJitaCheck) -> bool:
    if check.status != FittingBuyJitaCheckStatus.PENDING:
        return False
    if check.done_count > 0:
        return False
    age = (timezone.now() - check.updated_at).total_seconds()
    return age >= STALE_PENDING_SECONDS


def ensure_jita_check(
    order: FittingBuyOrder,
    user,
    *,
    force_refresh: bool = False,
    quiet: bool = False,
    type_ids: list[int] | None = None,
) -> FittingBuyJitaCheck | None:
    active = order.jita_checks.filter(
        status__in=[
            FittingBuyJitaCheckStatus.PENDING,
            FittingBuyJitaCheckStatus.RUNNING,
        ]
    ).first()
    if active:
        if force_refresh and not quiet:
            raise RuntimeError(
                "A Jita check is already running for this order."
            )
        if _is_stale_pending(active):
            logger.warning(
                "Re-enqueueing stale fitting buy Jita check %s (order %s)",
                active.id,
                order.id,
            )
            active.updated_at = timezone.now()
            active.save(update_fields=["updated_at"])
            start_jita_check_async(active.id)
        return active

    sync_order_items(order)
    if type_ids is not None:
        resolved = sorted({int(t) for t in type_ids})
    else:
        resolved = sorted(
            order.items.filter(buy_qty__gt=0).values_list(
                "eve_type_id", flat=True
            )
        )
    if not resolved:
        return None
    if len(resolved) > CHECK_MAX_TYPES:
        if quiet:
            return None
        raise RuntimeError(
            f"Too many types ({len(resolved)}; max {CHECK_MAX_TYPES})."
        )

    if quiet and not force_refresh:
        has_depth = (
            order.jita_checked_at is not None
            and not order.items.filter(
                buy_qty__gt=0, jita_sell_volume__isnull=True
            ).exists()
        )
        if has_depth:
            return None

    throttle_msg = check_user_throttle(user.id)
    if throttle_msg:
        if quiet:
            return None
        raise JitaThrottleError(throttle_msg)

    check = FittingBuyJitaCheck.objects.create(
        order=order,
        started_by=user,
        status=FittingBuyJitaCheckStatus.PENDING,
        force_refresh=force_refresh,
        type_ids=resolved,
        total_count=len(resolved),
    )
    mark_user_throttled(user.id)
    start_jita_check_async(check.id)
    return check
