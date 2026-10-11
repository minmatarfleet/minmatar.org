"""Paginated monthly inferred-sales volume for the Amamake report.

Slices the Redis-cached monthly ``by_type`` list (never re-aggregates fills).
Page size is fixed; sort/class are allowlisted. Markup and extra ISK use the
Forge Jita guide plus alliance Jita→Amamake freight (450 ISK/m³).
"""

from __future__ import annotations

import math
import re
from typing import Literal

from django.core.cache import cache
from django.utils import timezone
from eveuniverse.models import EveType

from market.helpers.inferred_sales_monthly import (
    CACHE_TTL_CLOSED_MONTH,
    CACHE_TTL_OPEN_MONTH,
    build_monthly_response,
    month_bounds,
)
from market.helpers.pricing import get_prices_by_type_id

PAGE_SIZE = 5
MAX_Q_LEN = 64
SORT_KEYS = ("isk", "units", "fills", "extra_isk", "markup")
SortKey = Literal["isk", "units", "fills", "extra_isk", "markup"]

# Alliance freight calculator: Jita → Amamake rate (volume charge only).
FREIGHT_ISK_PER_M3 = 450

PLEX_ADJACENT_GROUPS = frozenset({"Skill Injectors", "PLEX"})
PLEX_ADJACENT_TYPE_IDS = frozenset(
    {
        40519,  # Skill Extractor
        63188,  # Multiple Pilot Training
        34133,  # Multiple Pilot Training Certificate
        29668,  # 30 Day Pilot's License Extension (PLEX)
    }
)
MATERIAL_CATEGORIES = frozenset(
    {
        "Material",
        "Commodity",
        "Planetary Resources",
        "Planetary Commodities",
        "Asteroid",
        "Reaction Materials",
        "Colony Resources",
        "Gas",
        "Fullerite",
        "Booster Gas",
    }
)
MATERIAL_GROUPS = frozenset(
    {
        "Harvestable Cloud",
        "Compressed Gas",
        "Colony Reagents",
        "Fullerite",
        "Booster Gas",
    }
)

_SKIN_OR_BP = re.compile(r"\bSKIN\b|blueprint", re.IGNORECASE)

VOLUME_CACHE_KEY = (
    "market:inferred_sales_monthly_volume:{location_id}:{year}-{month:02d}"
)

CLASS_SLUG_LABELS: dict[str, str] = {
    "ships": "Ships",
    "modules": "Modules",
    "rigs": "Rigs",
    "charges": "Charges",
    "drones": "Drones",
    "plex-adjacent": "PLEX adjacent",
    "implants": "Implants",
    "materials-commodities": "Materials & commodities",
    "other": "Other",
}


def class_slug(name: str) -> str:
    slug = name.lower().replace("&", " ")
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def bucket_for_type(type_id: int, category: str, group: str) -> str:
    if group in PLEX_ADJACENT_GROUPS or type_id in PLEX_ADJACENT_TYPE_IDS:
        return "PLEX adjacent"
    if category == "Ship":
        return "Ships"
    if category == "Module" and re.search(r"rig", group, re.I):
        return "Rigs"
    if category in ("Module", "Subsystem"):
        return "Modules"
    if category == "Charge":
        return "Charges"
    if category in ("Drone", "Fighter"):
        return "Drones"
    if category == "Implant":
        return "Implants"
    if category in MATERIAL_CATEGORIES or group in MATERIAL_GROUPS:
        return "Materials & commodities"
    return "Other"


def is_skin_or_blueprint(name: str, category: str = "") -> bool:
    if category == "Blueprint":
        return True
    return bool(_SKIN_OR_BP.search(name or ""))


def _fmt_isk(value: float) -> str:
    mag = abs(value)
    if mag >= 1_000_000_000_000:
        body = f"{mag / 1_000_000_000_000:.2f}T"
    elif mag >= 100_000_000_000:
        body = f"{round(mag / 1_000_000_000)}B"
    elif mag >= 1_000_000_000:
        body = f"{mag / 1_000_000_000:.2f}B"
    elif mag >= 1_000_000:
        body = f"{mag / 1_000_000:.0f}M"
    else:
        body = f"{mag / 1_000:.0f}k"
    return f"-{body}" if value < 0 else body


def _enrich_rows(by_type: list[dict]) -> list[dict]:
    type_ids = [int(row["type_id"]) for row in by_type]
    # get_prices_by_type_id always hits default DB; history lives there in
    # production. Extract/test paths without history simply leave jita null.
    prices = get_prices_by_type_id(type_ids) if type_ids else {}

    volumes: dict[int, float] = {}
    if type_ids:
        try:
            qs = EveType.objects.filter(id__in=type_ids).values_list(
                "id", "volume"
            )
            volumes = {int(tid): float(vol or 0) for tid, vol in qs}
        except Exception:
            volumes = {}

    enriched: list[dict] = []
    for row in by_type:
        name = row.get("name") or ""
        category = row.get("category") or ""
        group = row.get("group") or ""
        if is_skin_or_blueprint(name, category):
            continue
        type_id = int(row["type_id"])
        units = int(row.get("units") or 0)
        isk = float(row.get("isk") or 0)
        fills = int(row.get("fills") or 0)
        amamake_avg = (isk / units) if units > 0 else 0.0
        jita = prices.get(type_id)
        freight = volumes.get(type_id, 0.0) * FREIGHT_ISK_PER_M3
        markup_pct = None
        extra_isk = None
        if jita is not None and jita > 0 and units > 0:
            landed = float(jita) + freight
            if landed > 0:
                margin = amamake_avg - landed
                markup_pct = round((margin / landed) * 1000) / 10
                extra_isk = margin * units

        bucket = bucket_for_type(type_id, category, group)
        enriched.append(
            {
                "type_id": type_id,
                "name": name,
                "group": group,
                "category": bucket,
                "fills": fills,
                "units": units,
                "isk": isk,
                "isk_label": _fmt_isk(isk),
                "amamake_avg": amamake_avg,
                "jita": float(jita) if jita is not None else None,
                "freight": freight,
                "markup_pct": markup_pct,
                "extra_isk": extra_isk,
                "extra_isk_label": (
                    _fmt_isk(extra_isk) if extra_isk is not None else None
                ),
            }
        )
    return enriched


def build_enriched_volume_rows(
    location_id: int,
    year: int,
    month: int,
    *,
    using: str | None = None,
) -> list[dict]:
    """Full enriched type list for a month (cached)."""
    key = VOLUME_CACHE_KEY.format(
        location_id=location_id, year=year, month=month
    )
    if using:
        key = f"{key}:using:{using}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    monthly = build_monthly_response(location_id, year, month, using=using)
    rows = _enrich_rows(monthly.get("by_type") or [])

    _, end = month_bounds(year, month)
    ttl = (
        CACHE_TTL_CLOSED_MONTH
        if end <= timezone.now()
        else CACHE_TTL_OPEN_MONTH
    )
    cache.set(key, rows, ttl)
    return rows


def _class_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        slug = class_slug(row["category"])
        counts[slug] = counts.get(slug, 0) + 1
    return counts


def _filter_by_class(
    rows: list[dict],
    sold_class: str,
    class_counts: dict[str, int],
) -> tuple[list[dict], str]:
    requested = (sold_class or "all").strip().lower()
    if not requested or requested == "all":
        return rows, requested
    if requested not in CLASS_SLUG_LABELS and requested not in class_counts:
        raise ValueError(f"unknown sold_class: {sold_class}")
    label = CLASS_SLUG_LABELS.get(requested)
    filtered = [
        row
        for row in rows
        if class_slug(row["category"]) == requested
        or (label is not None and row["category"] == label)
    ]
    return filtered, requested


def _filter_by_query(rows: list[dict], q: str) -> tuple[list[dict], str]:
    query = (q or "").strip()[:MAX_Q_LEN]
    if not query:
        return rows, query
    needle = query.casefold()
    type_id_match: int | None = None
    if query.isdigit():
        try:
            type_id_match = int(query)
        except ValueError:
            type_id_match = None

    def matches(row: dict) -> bool:
        if type_id_match is not None and row.get("type_id") == type_id_match:
            return True
        name = (row.get("name") or "").casefold()
        return needle in name

    return [row for row in rows if matches(row)], query


def _sort_rows(rows: list[dict], sort: str) -> list[dict]:
    def sort_key(row: dict):
        if sort == "markup":
            val = row.get("markup_pct")
            return (val is not None, val if val is not None else 0)
        if sort == "extra_isk":
            val = row.get("extra_isk")
            return (val is not None, val if val is not None else 0)
        return row.get(sort) or 0

    return sorted(rows, key=sort_key, reverse=True)


def build_volume_page(
    location_id: int,
    year: int,
    month: int,
    *,
    page: int = 1,
    sort: str = "isk",
    sold_class: str = "all",
    q: str = "",
    using: str | None = None,
) -> dict:
    """Return one page of the monthly volume table."""
    if sort not in SORT_KEYS:
        raise ValueError(f"sort must be one of: {', '.join(SORT_KEYS)}")
    if page < 1:
        raise ValueError("page must be >= 1")

    rows = build_enriched_volume_rows(location_id, year, month, using=using)
    class_counts = _class_counts(rows)
    filtered, requested = _filter_by_class(rows, sold_class, class_counts)
    filtered, query = _filter_by_query(filtered, q)
    ordered = _sort_rows(filtered, sort)

    total = len(ordered)
    total_pages = max(1, math.ceil(total / PAGE_SIZE)) if total else 1
    page = min(page, total_pages)
    start = (page - 1) * PAGE_SIZE
    page_rows = ordered[start : start + PAGE_SIZE]

    classes = [
        {
            "slug": slug,
            "label": CLASS_SLUG_LABELS.get(slug, slug),
            "count": count,
        }
        for slug, count in sorted(
            class_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]

    return {
        "location_id": location_id,
        "year": year,
        "month": month,
        "page": page,
        "page_size": PAGE_SIZE,
        "total": total,
        "total_pages": total_pages,
        "sort": sort,
        "sold_class": requested,
        "q": query,
        "classes": classes,
        "rows": page_rows,
    }
