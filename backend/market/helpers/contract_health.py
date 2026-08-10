"""Contract-side staging supply health."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.db.models import (
    Count,
    DecimalField,
    Max,
    Min,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from eveuniverse.models import EveType

from market.helpers.contract_match import fitting_type_quantities_bulk
from market.helpers.contract_stock import outstanding_stock_q
from market.helpers.health_common import (
    VOLUME_DAYS_1,
    VOLUME_DAYS_3,
    VOLUME_DAYS_7,
    VOLUME_DAYS_30,
    VOLUME_DAYS_90,
    days_of_stock,
    fitting_baseline_isk,
    forge_baseline_by_type,
    health_pct,
    market_active_locations,
    ship_size_rank,
    windowed_count,
)
from market.helpers.price_viability import is_price_viable
from market.helpers.readiness import fitting_readiness, shortfall
from market.models import (
    EveMarketContract,
    EveMarketContractExpectation,
    EveMarketContractItem,
)


def _contract_contents_by_id(
    contract_ids: list[int],
) -> dict[int, dict[int, int]]:
    """``{contract_id: {type_id: qty}}`` for included ESI contract items."""
    if not contract_ids:
        return {}
    contents: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for row in EveMarketContractItem.objects.filter(
        contract_id__in=contract_ids,
        is_included=True,
    ).values("contract_id", "type_id", "quantity"):
        contents[row["contract_id"]][int(row["type_id"])] += int(
            row["quantity"] or 1
        )
    return {cid: dict(qtys) for cid, qtys in contents.items()}


def build_contract_health(  # noqa: C901
    *, location_id: int | None = None
) -> dict:
    """
    Contract-side staging supply health for one or all market-active locations.
    """
    locations = market_active_locations(location_id)
    if not locations:
        return {"by_location": {}}

    location_pks = [loc.pk for loc in locations]

    expectations = list(
        EveMarketContractExpectation.objects.filter(
            location_id__in=location_pks
        ).select_related("fitting", "location")
    )
    expectation_fittings = list(
        {
            expectation.fitting_id: expectation.fitting
            for expectation in expectations
            if expectation.fitting_id is not None
        }.values()
    )
    # EFT baselines are a fallback when a contract has no fetched items yet.
    fitting_qtys = fitting_type_quantities_bulk(expectation_fittings)

    outstanding_contracts = list(
        EveMarketContract.objects.filter(
            outstanding_stock_q(),
            location_id__in=location_pks,
            fitting_id__isnull=False,
        ).values("id", "location_id", "fitting_id", "price")
    )
    contents_by_contract = _contract_contents_by_id(
        [row["id"] for row in outstanding_contracts]
    )
    contract_type_ids = {
        type_id for qtys in fitting_qtys.values() for type_id in qtys
    }
    for qtys in contents_by_contract.values():
        contract_type_ids.update(qtys)
    contract_baseline_by_type = forge_baseline_by_type(
        sorted(contract_type_ids)
    )
    fitting_baseline_by_fit = {
        fit_id: fitting_baseline_isk(qtys, contract_baseline_by_type)
        for fit_id, qtys in fitting_qtys.items()
    }

    outstanding: dict[tuple[int, int], int] = defaultdict(int)
    viable_outstanding: dict[tuple[int, int], int] = defaultdict(int)
    for row in outstanding_contracts:
        fitting_id = row["fitting_id"]
        key = (row["location_id"], fitting_id)
        outstanding[key] += 1
        contents = contents_by_contract.get(row["id"])
        if contents:
            baseline = fitting_baseline_isk(
                contents, contract_baseline_by_type
            )
        else:
            baseline = fitting_baseline_by_fit.get(fitting_id)
        if is_price_viable(row["price"], baseline):
            viable_outstanding[key] += 1

    now = timezone.now()
    since_1 = now - timedelta(days=VOLUME_DAYS_1)
    since_3 = now - timedelta(days=VOLUME_DAYS_3)
    since_7 = now - timedelta(days=VOLUME_DAYS_7)
    since_30 = now - timedelta(days=VOLUME_DAYS_30)
    since_90 = now - timedelta(days=VOLUME_DAYS_90)

    def _finished_window_count(since):
        return windowed_count(since, timestamp_field="completed_at")

    units_1d_by_loc_fit: dict[tuple[int, int], int] = {}
    units_3d_by_loc_fit: dict[tuple[int, int], int] = {}
    weekly_units_by_loc_fit: dict[tuple[int, int], int] = {}
    units_30d_by_loc_fit: dict[tuple[int, int], int] = {}
    units_90d_by_loc_fit: dict[tuple[int, int], int] = {}
    contract_history_days = 0
    finished_qs = EveMarketContract.objects.filter(
        status="finished",
        location_id__in=location_pks,
        fitting_id__isnull=False,
        completed_at__gte=since_90,
    )
    for row in finished_qs.values("location_id", "fitting_id").annotate(
        units_1d=_finished_window_count(since_1),
        units_3d=_finished_window_count(since_3),
        units_7d=_finished_window_count(since_7),
        units_30d=_finished_window_count(since_30),
        units_90d=Count("id"),
    ):
        key = (row["location_id"], row["fitting_id"])
        units_1d_by_loc_fit[key] = row["units_1d"]
        units_3d_by_loc_fit[key] = row["units_3d"]
        weekly_units_by_loc_fit[key] = row["units_7d"]
        units_30d_by_loc_fit[key] = row["units_30d"]
        units_90d_by_loc_fit[key] = row["units_90d"]

    earliest_finished = finished_qs.aggregate(earliest=Min("completed_at"))[
        "earliest"
    ]
    if earliest_finished is not None:
        contract_history_days = max(
            1,
            int((now - earliest_finished).total_seconds() // 86400) + 1,
        )

    rows = []
    contract_fill_ratios_by_loc: dict[int, list[float]] = defaultdict(list)
    contract_viable_fill_ratios_by_loc: dict[int, list[float]] = defaultdict(
        list
    )
    contract_targets_by_loc: dict[int, int] = defaultdict(int)
    contract_listed_by_loc: dict[int, int] = defaultdict(int)
    contract_fulfilled_by_loc: dict[int, int] = defaultdict(int)
    contract_viable_fulfilled_by_loc: dict[int, int] = defaultdict(int)
    for expectation in expectations:
        key = (expectation.location_id, expectation.fitting_id)
        current = outstanding.get(key, 0)
        viable = viable_outstanding.get(key, 0)
        desired = expectation.desired_quantity
        if desired > 0:
            ratio = min(1.0, current / desired)
            contract_fill_ratios_by_loc[expectation.location_id].append(ratio)
            contract_targets_by_loc[expectation.location_id] += 1
            if current >= desired:
                contract_fulfilled_by_loc[expectation.location_id] += 1
            # Viability = price quality of what is listed, not empty shelves.
            if current > 0:
                viable_ratio = min(1.0, viable / current)
                contract_viable_fill_ratios_by_loc[
                    expectation.location_id
                ].append(viable_ratio)
                contract_listed_by_loc[expectation.location_id] += 1
                if viable >= current:
                    contract_viable_fulfilled_by_loc[
                        expectation.location_id
                    ] += 1
        level = fitting_readiness(current, desired)
        if level in ("ready", "unknown"):
            continue
        weekly_units = weekly_units_by_loc_fit.get(key, 0)
        rows.append(
            {
                "location_id": expectation.location.location_id,
                "location_name": expectation.location.location_name,
                "short_name": expectation.location.short_name or "",
                "fitting_id": expectation.fitting_id,
                "fitting_name": expectation.fitting.name,
                "ship_id": expectation.fitting.ship_id,
                "current_quantity": current,
                "viable_quantity": viable,
                "expected_quantity": desired,
                "shortfall": shortfall(current, desired),
                "readiness": level,
                "expectation_id": expectation.id,
                "units_1d": units_1d_by_loc_fit.get(key, 0),
                "units_3d": units_3d_by_loc_fit.get(key, 0),
                "weekly_units": weekly_units,
                "units_30d": units_30d_by_loc_fit.get(key, 0),
                "units_90d": units_90d_by_loc_fit.get(key, 0),
                "days_of_stock": days_of_stock(current, weekly_units),
            }
        )

    ship_ids = {row["ship_id"] for row in rows}
    group_by_ship_id = dict(
        EveType.objects.filter(id__in=ship_ids).values_list(
            "id", "eve_group__name"
        )
    )

    rows.sort(
        key=lambda row: (
            ship_size_rank(group_by_ship_id.get(row["ship_id"])),
            0 if row["readiness"] == "empty" else 1,
            -row["shortfall"],
            row["fitting_name"],
        )
    )

    latest_contract_by_loc = dict(
        EveMarketContract.objects.filter(location_id__in=location_pks)
        .values("location_id")
        .annotate(latest=Max("last_updated"))
        .values_list("location_id", "latest")
    )

    isk_decimal_field = DecimalField(max_digits=32, decimal_places=2)
    contracts_isk_by_loc = {
        row["location_id"]: float(row["total"] or 0)
        for row in EveMarketContract.objects.filter(
            location_id__in=location_pks,
            status="outstanding",
        )
        .values("location_id")
        .annotate(
            total=Coalesce(
                Sum("price"), Value(0, output_field=isk_decimal_field)
            )
        )
    }

    by_location: dict[int, dict] = {}
    for loc in locations:
        loc_pk = loc.pk
        loc_rows = [
            row for row in rows if row["location_id"] == loc.location_id
        ]
        loc_latest_contract = latest_contract_by_loc.get(loc_pk)
        by_location[loc.location_id] = {
            "synced_at": (
                loc_latest_contract.isoformat()
                if loc_latest_contract
                else None
            ),
            "rows": loc_rows,
            "summary": {
                "health_pct": health_pct(
                    contract_fill_ratios_by_loc.get(loc_pk, [])
                ),
                "viability_pct": health_pct(
                    contract_viable_fill_ratios_by_loc.get(loc_pk, [])
                ),
                "targets": contract_targets_by_loc.get(loc_pk, 0),
                "listed_targets": contract_listed_by_loc.get(loc_pk, 0),
                "fulfilled": contract_fulfilled_by_loc.get(loc_pk, 0),
                "viable_fulfilled": contract_viable_fulfilled_by_loc.get(
                    loc_pk, 0
                ),
                "isk": round(contracts_isk_by_loc.get(loc_pk, 0.0), 2),
                "history_days": contract_history_days,
            },
        }

    return {"by_location": by_location}
