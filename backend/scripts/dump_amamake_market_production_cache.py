#!/usr/bin/env python
"""Read-only dump of production Amamake market series for the report extractor.

Writes JSON under frontend/app/.cache/amamake-market/ so
``npm run amamake:extract`` can publish from production inferred sales,
finished contracts, and Forge Jita guide prices without hitting the
(not-yet-deployed) monthly API.

Never writes to production_readonly.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
django.setup()

from django.db.models import Max  # noqa: E402

from fittings.models import EveFitting  # noqa: E402
from market.helpers.inferred_sales_monthly import (  # noqa: E402
    build_monthly_response,
    month_bounds,
)
from market.models import EveMarketContract, EveMarketItemHistory  # noqa: E402

DB = "production_readonly"
LOCATION_ID = 1_022_167_642_188
FORGE_REGION_ID = 10_000_002
CACHE_DIR = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "app"
    / ".cache"
    / "amamake-market"
)


def _json(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(type(value))


def write_json(name: str, payload: dict) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / name
    path.write_text(json.dumps(payload, default=_json))
    return path


def dump_sales(year: int, month: int) -> dict:
    payload = build_monthly_response(
        LOCATION_ID, year, month, using=DB
    )
    payload["source"] = "production_readonly"
    path = write_json(
        f"sales-{LOCATION_ID}-{year}-{month:02d}.json", payload
    )
    days = [row["date"] for row in payload["days"]]
    print(
        f"sales {year}-{month:02d}: {payload['totals']['fills']} fills · "
        f"{len(days)} days · {path.name}"
    )
    print(f"  dates {days}")
    start, end = month_bounds(year, month)
    expected = set()
    cursor = start.date()
    while cursor < end.date():
        expected.add(cursor.isoformat())
        cursor += timedelta(days=1)
    missing = sorted(expected - set(days))
    print(f"  missing {missing or 'none'}")
    return payload


def dump_contracts(year: int, month: int) -> dict:
    start, end = month_bounds(year, month)
    rows = list(
        EveMarketContract.objects.using(DB)
        .filter(
            location_id=LOCATION_ID,
            status="finished",
            completed_at__gte=start,
            completed_at__lt=end,
        )
        .values(
            "id",
            "price",
            "completed_at",
            "fitting_id",
            "title",
        )
    )
    fitting_ids = {row["fitting_id"] for row in rows if row["fitting_id"]}
    ships = {
        fitting.id: fitting.ship_id
        for fitting in EveFitting.all_objects.using(DB).filter(id__in=fitting_ids)
    }
    payload = {
        "source": "production_readonly",
        "location_id": LOCATION_ID,
        "year": year,
        "month": month,
        "contracts": [
            {
                "id": row["id"],
                "price": float(row["price"] or 0),
                "completed_at": row["completed_at"].isoformat()
                if row["completed_at"]
                else None,
                "fitting_id": row["fitting_id"],
                "ship_id": ships.get(row["fitting_id"]),
                "title": row["title"],
            }
            for row in rows
        ],
    }
    path = write_json(
        f"contracts-{LOCATION_ID}-{year}-{month:02d}.json", payload
    )
    print(
        f"contracts {year}-{month:02d}: {len(rows)} finished · "
        f"{sum(1 for row in rows if row['fitting_id'])} matched · {path.name}"
    )
    return payload


def dump_jita(type_ids: set[int], year: int, month: int) -> dict:
    start, end = month_bounds(year, month)
    window_start = start.date() - timedelta(days=7)
    as_of = (end - timedelta(seconds=1)).date()
    latest = (
        EveMarketItemHistory.objects.using(DB)
        .filter(
            region_id=FORGE_REGION_ID,
            item_id__in=type_ids,
            date__gte=window_start,
            date__lte=as_of,
        )
        .values("item_id")
        .annotate(latest=Max("date"))
    )
    latest_by_item = {row["item_id"]: row["latest"] for row in latest}
    prices: dict[str, float] = {}
    if latest_by_item:
        for row in EveMarketItemHistory.objects.using(DB).filter(
            region_id=FORGE_REGION_ID,
            item_id__in=latest_by_item.keys(),
            date__gte=window_start,
            date__lte=as_of,
        ).values("item_id", "date", "average"):
            if row["date"] == latest_by_item.get(row["item_id"]):
                prices[str(row["item_id"])] = float(row["average"] or 0)
    payload = {
        "source": "production_readonly",
        "region_id": FORGE_REGION_ID,
        "as_of": as_of.isoformat(),
        "types": len(type_ids),
        "priced": len(prices),
        "prices": prices,
    }
    path = write_json(f"jita-{year}-{month:02d}.json", payload)
    print(
        f"jita {year}-{month:02d}: {len(prices)}/{len(type_ids)} types · "
        f"as of {as_of} · {path.name}"
    )
    return payload


def main() -> None:
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    month = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    print(f"dumping production_readonly → {CACHE_DIR}")
    sales = dump_sales(year, month)
    prev_sales = dump_sales(prev_year, prev_month)
    dump_contracts(year, month)
    dump_contracts(prev_year, prev_month)
    type_ids = {int(row["type_id"]) for row in sales.get("by_type", [])}
    dump_jita(type_ids, year, month)
    prev_type_ids = {int(row["type_id"]) for row in prev_sales.get("by_type", [])}
    dump_jita(prev_type_ids, prev_year, prev_month)


if __name__ == "__main__":
    main()
