"""Supply chain insights for the product detail page.

Who builds each product, how many were bought (industry orders, market
sales, doctrine contracts), how many ships sit in hangars and how many were
lost. The numbers scan industry jobs, killmails, assets and market history,
so they are computed for every product in one Celery pass and served from
the cache; a request only reads the cache and, on a miss, queues a refresh.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone as dt_timezone

from django.db.models import Q
from django.utils import timezone

from eveonline.helpers.corporations.safe_cache import (
    cache_add,
    cache_delete,
    cache_get,
    cache_set,
)
from eveonline.models import (
    EveAlliance,
    EveCharacter,
    EveCharacterAsset,
    EveCharacterIndustryJob,
    EveCharacterKillmail,
    EveCorporationIndustryJob,
    EvePlayer,
)
from eveuniverse.models import EveIndustryActivityProduct, EveMarketPrice
from industry.models import IndustryOrderItem, IndustryProduct
from market.models import (
    EveMarketContractItem,
    EveMarketInferredSale,
    EveMarketItemOrder,
)

logger = logging.getLogger(__name__)

INSIGHTS_TTL_SECONDS = 6 * 60 * 60
REFRESH_LOCK_SECONDS = 10 * 60
_INSIGHTS_KEY = "industry_product_insights:v1:{product_id}"
_LOCK_KEY = "industry_product_insights:refreshing"

WINDOW_DAYS = 90
RECENT_DAYS = 30
WEEKS = 13
TOP_BUILDERS = 12
TOP_LOCATIONS = 6
RECENT_ORDERS = 8
RECENT_LOSSES = 8

PRODUCTION_ACTIVITIES = (1, 11)  # manufacturing, reactions
FINISHED_JOB_STATUSES = ("delivered", "ready")
RUNNING_JOB_STATUSES = ("active", "paused")


def _week_start(moment: datetime) -> datetime:
    day = moment.astimezone(dt_timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return day - timedelta(days=day.weekday())


class _Weeks:
    """Monday-aligned weekly buckets covering the last WEEKS weeks."""

    def __init__(self, now: datetime):
        last = _week_start(now)
        self.starts = [
            last - timedelta(weeks=i) for i in range(WEEKS - 1, -1, -1)
        ]
        self.first = self.starts[0]

    def index(self, moment: datetime) -> int | None:
        if moment is None or moment < self.first:
            return None
        i = (_week_start(moment) - self.first).days // 7
        return i if 0 <= i < WEEKS else None


def _empty_insights(product: IndustryProduct, weeks: _Weeks) -> dict:
    is_ship = product.eve_type.eve_group.eve_category_id == 6
    return {
        "type_id": product.eve_type_id,
        "is_ship": is_ship,
        "window_days": WINDOW_DAYS,
        "recent_days": RECENT_DAYS,
        "unit_price": None,
        "built": {
            "units_30d": 0,
            "units_90d": 0,
            "jobs_90d": 0,
            "builders_90d": 0,
            "running_units": 0,
            "running_jobs": 0,
            "last_built_at": None,
        },
        "builders": [],
        "corporations": [],
        "orders": {
            "open_orders": 0,
            "open_units": 0,
            "open_assigned_units": 0,
            "open_delivered_units": 0,
            "ordered_units_90d": 0,
            "recent": [],
        },
        "sales": {
            "market_units_30d": 0,
            "market_units_90d": 0,
            "contract_units_30d": 0,
            "contract_units_90d": 0,
            "listed_units": 0,
            "lowest_listed_price": None,
            "outstanding_contracts": 0,
            "locations": [],
        },
        "hangars": (
            {"units": 0, "pilots": 0, "locations": []} if is_ship else None
        ),
        "losses": (
            {"units_30d": 0, "units_90d": 0, "recent": []} if is_ship else None
        ),
        "weekly": [
            {"week_start": start, "built": 0, "sold": 0, "lost": 0}
            for start in weeks.starts
        ],
    }


def _primary_by_character(character_ids) -> dict[int, tuple[int, str]]:
    """character_id -> (primary character_id, primary name), for known pilots."""
    rows = list(
        EveCharacter.objects.filter(
            character_id__in=character_ids
        ).values_list("character_id", "character_name", "user_id")
    )
    primaries = {
        user_id: (cid, name or "")
        for user_id, cid, name in EvePlayer.objects.filter(
            user_id__in={r[2] for r in rows if r[2]},
            primary_character__isnull=False,
        ).values_list(
            "user_id",
            "primary_character__character_id",
            "primary_character__character_name",
        )
    }
    out = {}
    for cid, name, user_id in rows:
        out[cid] = primaries.get(user_id) or (cid, name or "")
    return out


def _blueprints_by_product(type_ids) -> dict[tuple[int, int], list]:
    """(blueprint_type_id, activity_id) -> [(product_type_id, qty_per_run)]."""
    mapping = defaultdict(list)
    for bid, aid, tid, qty in EveIndustryActivityProduct.objects.filter(
        product_eve_type_id__in=type_ids,
        activity_id__in=PRODUCTION_ACTIVITIES,
    ).values_list(
        "eve_type_id", "activity_id", "product_eve_type_id", "quantity"
    ):
        mapping[(bid, aid)].append((tid, qty or 1))
    return mapping


def _production_jobs(blueprints, since) -> list[tuple]:
    """Character and corporation jobs for these blueprints, recent or running.

    Rows: (blueprint, activity, runs, status, end, installer, corp id, name).
    """
    match = Q()
    for bid, aid in blueprints:
        match |= Q(blueprint_type_id=bid, activity_id=aid)
    window = Q(end_date__gte=since) | Q(status__in=RUNNING_JOB_STATUSES)
    fields = (
        "blueprint_type_id",
        "activity_id",
        "runs",
        "status",
        "end_date",
        "installer_id",
    )
    return [
        (*row, None, "")
        for row in EveCharacterIndustryJob.objects.filter(
            match, window
        ).values_list(*fields)
    ] + list(
        EveCorporationIndustryJob.objects.filter(match, window).values_list(
            *fields, "corporation__corporation_id", "corporation__name"
        )
    )


def _add_finished_build(data, builders, units, end_date, builder, context):
    """Count one finished job towards a product's totals and its builder."""
    recent_since, weeks = context
    built = data["built"]
    built["units_90d"] += units
    built["jobs_90d"] += 1
    if end_date >= recent_since:
        built["units_30d"] += units
    if not built["last_built_at"] or end_date > built["last_built_at"]:
        built["last_built_at"] = end_date
    week = weeks.index(end_date)
    if week is not None:
        data["weekly"][week]["built"] += units
    pid, pname = builder
    row = builders.setdefault(
        pid,
        {
            "character_id": pid,
            "character_name": pname,
            "units": 0,
            "jobs": 0,
            "last_built_at": None,
        },
    )
    row["units"] += units
    row["jobs"] += 1
    if not row["last_built_at"] or end_date > row["last_built_at"]:
        row["last_built_at"] = end_date


def _fill_builders(insights, type_ids, now, weeks):
    blueprints = _blueprints_by_product(type_ids)
    if not blueprints:
        return
    since = now - timedelta(days=WINDOW_DAYS)
    context = (now - timedelta(days=RECENT_DAYS), weeks)
    jobs = _production_jobs(blueprints, since)
    primaries = _primary_by_character({job[5] for job in jobs})
    corp_names = {job[6]: job[7] for job in jobs if job[6]}

    builders = defaultdict(dict)  # type_id -> primary id -> row
    corporations = defaultdict(Counter)  # type_id -> corp id -> units
    for bid, aid, runs, status, end_date, installer, corp_id, _ in jobs:
        running = status in RUNNING_JOB_STATUSES and end_date > now
        finished = status in FINISHED_JOB_STATUSES or (
            status in RUNNING_JOB_STATUSES and not running
        )
        for tid, qty in blueprints.get((bid, aid), []):
            built = insights[tid]["built"]
            if running:
                built["running_units"] += runs * qty
                built["running_jobs"] += 1
            elif finished and end_date >= since:
                _add_finished_build(
                    insights[tid],
                    builders[tid],
                    runs * qty,
                    end_date,
                    primaries.get(installer, (installer, "")),
                    context,
                )
                if corp_id:
                    corporations[tid][corp_id] += runs * qty

    for tid, rows in builders.items():
        ranked = sorted(rows.values(), key=lambda r: r["units"], reverse=True)
        insights[tid]["built"]["builders_90d"] = len(ranked)
        insights[tid]["builders"] = ranked[:TOP_BUILDERS]
    for tid, counts in corporations.items():
        insights[tid]["corporations"] = [
            {
                "corporation_id": cid,
                "corporation_name": corp_names.get(cid) or "",
                "units": units,
            }
            for cid, units in counts.most_common(TOP_LOCATIONS)
        ]


def _fill_orders(insights, type_ids, now):
    since = now - timedelta(days=WINDOW_DAYS)
    items = (
        IndustryOrderItem.objects.filter(eve_type_id__in=type_ids)
        .filter(
            Q(order__fulfilled_at__isnull=True)
            | Q(order__created_at__gte=since)
        )
        .select_related("order", "order__character")
        .prefetch_related("assignments")
        .order_by("-order__created_at")
    )
    for item in items:
        order = item.order
        orders = insights[item.eve_type_id]["orders"]
        assigned = sum(a.quantity for a in item.assignments.all())
        delivered = sum(
            a.delivered_quantity or 0 for a in item.assignments.all()
        )
        if order.created_at >= since:
            orders["ordered_units_90d"] += item.quantity
        if order.fulfilled_at is None:
            orders["open_orders"] += 1
            orders["open_units"] += item.quantity
            orders["open_assigned_units"] += assigned
            orders["open_delivered_units"] += delivered
        if len(orders["recent"]) < RECENT_ORDERS:
            orders["recent"].append(
                {
                    "order_id": order.pk,
                    "public_short_code": order.public_short_code,
                    "character_id": (
                        order.character.character_id
                        if order.character_id
                        else None
                    ),
                    "character_name": (
                        order.character.character_name
                        if order.character_id
                        else ""
                    ),
                    "created_at": order.created_at,
                    "needed_by": order.needed_by,
                    "fulfilled_at": order.fulfilled_at,
                    "quantity": item.quantity,
                    "assigned": assigned,
                    "delivered": delivered,
                }
            )


def _fill_sales(insights, type_ids, now, weeks):
    since = now - timedelta(days=WINDOW_DAYS)
    recent_since = now - timedelta(days=RECENT_DAYS)
    locations = defaultdict(Counter)
    for (
        tid,
        qty,
        inferred_at,
        location,
    ) in EveMarketInferredSale.objects.filter(
        item_id__in=type_ids, inferred_at__gte=since
    ).values_list(
        "item_id", "quantity", "inferred_at", "location__location_name"
    ):
        sales = insights[tid]["sales"]
        sales["market_units_90d"] += qty
        if inferred_at >= recent_since:
            sales["market_units_30d"] += qty
            locations[tid][location or "Unknown"] += qty
        week = weeks.index(inferred_at)
        if week is not None:
            insights[tid]["weekly"][week]["sold"] += qty

    for tid, qty, completed_at in EveMarketContractItem.objects.filter(
        type_id__in=type_ids,
        is_included=True,
        contract__status="finished",
        contract__completed_at__gte=since,
    ).values_list("type_id", "quantity", "contract__completed_at"):
        sales = insights[tid]["sales"]
        sales["contract_units_90d"] += qty
        if completed_at >= recent_since:
            sales["contract_units_30d"] += qty
        week = weeks.index(completed_at)
        if week is not None:
            insights[tid]["weekly"][week]["sold"] += qty

    for tid, count in Counter(
        EveMarketContractItem.objects.filter(
            type_id__in=type_ids,
            is_included=True,
            contract__status="outstanding",
        ).values_list("type_id", flat=True)
    ).items():
        insights[tid]["sales"]["outstanding_contracts"] = count

    for tid, qty, price in EveMarketItemOrder.objects.filter(
        item_id__in=type_ids, is_buy_order=False
    ).values_list("item_id", "quantity", "price"):
        sales = insights[tid]["sales"]
        sales["listed_units"] += qty
        lowest = sales["lowest_listed_price"]
        if lowest is None or price < lowest:
            sales["lowest_listed_price"] = float(price)

    for tid, counts in locations.items():
        insights[tid]["sales"]["locations"] = [
            {"location_name": name, "units": units}
            for name, units in counts.most_common(TOP_LOCATIONS)
        ]


def _fill_hangars(insights, ship_type_ids):
    if not ship_type_ids:
        return
    alliance_ids = list(
        EveAlliance.objects.values_list("alliance_id", flat=True)
    )
    rows = EveCharacterAsset.objects.filter(
        type_id__in=ship_type_ids,
        character__alliance_id__in=alliance_ids,
    ).values_list(
        "type_id", "location_name", "character__user_id", "character_id"
    )
    locations = defaultdict(Counter)
    pilots = defaultdict(set)
    for tid, location, user_id, character_pk in rows:
        insights[tid]["hangars"]["units"] += 1
        locations[tid][location or "Unknown"] += 1
        pilots[tid].add(("u", user_id) if user_id else ("c", character_pk))
    for tid, counts in locations.items():
        hangars = insights[tid]["hangars"]
        hangars["pilots"] = len(pilots[tid])
        hangars["locations"] = [
            {"location_name": name, "units": units}
            for name, units in counts.most_common(TOP_LOCATIONS)
        ]


def _fill_losses(insights, ship_type_ids, now, weeks):
    if not ship_type_ids:
        return
    since = min(now - timedelta(days=WINDOW_DAYS), weeks.first)
    recent_since = now - timedelta(days=RECENT_DAYS)
    alliance_ids = list(
        EveAlliance.objects.values_list("alliance_id", flat=True)
    )
    # Several of our pilots can hold the same killmail; count each kill once.
    seen = set()
    rows = (
        EveCharacterKillmail.objects.filter(
            killmail_time__gte=since,
            ship_type_id__in=ship_type_ids,
            victim_alliance_id__in=alliance_ids,
        )
        .order_by("-killmail_time")
        .values_list(
            "killmail_id",
            "killmail_time",
            "ship_type_id",
            "victim_character_id",
            "solar_system_id",
        )
    )
    victims = []
    for killmail_id, moment, tid, victim_id, system_id in rows:
        if killmail_id in seen:
            continue
        seen.add(killmail_id)
        losses = insights[tid]["losses"]
        if moment >= now - timedelta(days=WINDOW_DAYS):
            losses["units_90d"] += 1
        if moment >= recent_since:
            losses["units_30d"] += 1
        week = weeks.index(moment)
        if week is not None:
            insights[tid]["weekly"][week]["lost"] += 1
        if len(losses["recent"]) < RECENT_LOSSES:
            losses["recent"].append(
                {
                    "killmail_id": killmail_id,
                    "killmail_time": moment,
                    "character_id": victim_id,
                    "character_name": "",
                    "solar_system_id": system_id,
                }
            )
            victims.append(losses["recent"][-1])
    names = dict(
        EveCharacter.objects.filter(
            character_id__in={v["character_id"] for v in victims}
        ).values_list("character_id", "character_name")
    )
    for victim in victims:
        victim["character_name"] = names.get(victim["character_id"], "")


def compute_product_insights(now: datetime | None = None) -> dict[int, dict]:
    """Insights for every industry product, keyed by product id."""
    now = now or timezone.now()
    weeks = _Weeks(now)
    products = list(
        IndustryProduct.objects.select_related("eve_type__eve_group")
    )
    by_type = {p.eve_type_id: _empty_insights(p, weeks) for p in products}
    type_ids = list(by_type)
    ship_type_ids = [tid for tid, data in by_type.items() if data["is_ship"]]

    prices = dict(
        EveMarketPrice.objects.filter(eve_type_id__in=type_ids).values_list(
            "eve_type_id", "average_price"
        )
    )
    for tid, price in prices.items():
        by_type[tid]["unit_price"] = float(price) if price else None

    _fill_builders(by_type, type_ids, now, weeks)
    _fill_orders(by_type, type_ids, now)
    _fill_sales(by_type, type_ids, now, weeks)
    _fill_hangars(by_type, ship_type_ids)
    _fill_losses(by_type, ship_type_ids, now, weeks)

    return {
        p.pk: {**by_type[p.eve_type_id], "generated_at": now} for p in products
    }


def refresh_product_insights() -> int:
    insights = compute_product_insights()
    for product_id, data in insights.items():
        cache_set(
            _INSIGHTS_KEY.format(product_id=product_id),
            data,
            INSIGHTS_TTL_SECONDS,
        )
    cache_delete(_LOCK_KEY)
    return len(insights)


def product_insights(product_id: int) -> dict | None:
    """Cached insights, or None after queueing a refresh. Never computes inline."""
    key = _INSIGHTS_KEY.format(product_id=product_id)
    data = cache_get(key)
    if data is not None:
        return data
    # cache.add is atomic, so only one request per window queues the work.
    if cache_add(_LOCK_KEY, True, REFRESH_LOCK_SECONDS):
        # Imported here: the task module imports this helper.
        from industry.tasks import (  # pylint: disable=import-outside-toplevel
            refresh_product_insights_task,
        )

        refresh_product_insights_task.delay()
    # Eager Celery (tests) fills the cache during the call above.
    return cache_get(key)
