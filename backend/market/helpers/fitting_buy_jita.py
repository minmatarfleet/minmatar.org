"""Live Jita sell depth for fitting buy orders (type-filtered ESI)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Iterable

from django.core.cache import cache
from django.utils import timezone
from eveonline.client import get_region_market_orders_pages
from eveonline.models import EveLocation

JITA_DEPTH_CACHE_TTL = 300
# v3: band skipped when best sell < JITA_DEPTH_BAND_MIN_PRICE.
JITA_DEPTH_CACHE_PREFIX = "market:jita_sell_depth:v3"
DEFAULT_CONCURRENCY = 8

# Usable depth = sells within this fraction of best sell (when band applies).
JITA_DEPTH_PRICE_BAND = Decimal("0.10")
# Below this best-sell floor, count the full book (tiny absolute % jumps).
JITA_DEPTH_BAND_MIN_PRICE = Decimal("1000000")


@dataclass(frozen=True)
class JitaSellDepth:
    type_id: int
    volume: int
    order_count: int
    sell_min: Decimal | None
    fetched_at: str
    from_cache: bool = False
    volume_total: int = 0
    sell_band_max: Decimal | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.sell_min is not None:
            data["sell_min"] = str(self.sell_min)
        if self.sell_band_max is not None:
            data["sell_band_max"] = str(self.sell_band_max)
        return data


@dataclass(frozen=True)
class BandedSellDepth:
    volume: int
    volume_total: int
    order_count: int
    sell_min: Decimal | None
    sell_band_max: Decimal | None


def baseline_jita_location() -> EveLocation | None:
    return (
        EveLocation.objects.filter(price_baseline=True)
        .exclude(region_id__isnull=True)
        .first()
    )


def _cache_key(location_id: int, type_id: int) -> str:
    return f"{JITA_DEPTH_CACHE_PREFIX}:{location_id}:{type_id}"


def compute_banded_sell_depth(
    orders: Iterable[tuple[Decimal, int]],
    *,
    price_band: Decimal = JITA_DEPTH_PRICE_BAND,
    band_min_price: Decimal = JITA_DEPTH_BAND_MIN_PRICE,
) -> BandedSellDepth:
    levels = [(price, int(volume)) for price, volume in orders if volume]
    volume_total = sum(volume for _, volume in levels)
    if not levels:
        return BandedSellDepth(
            volume=0,
            volume_total=0,
            order_count=0,
            sell_min=None,
            sell_band_max=None,
        )

    levels.sort(key=lambda row: row[0])
    sell_min = levels[0][0]
    apply_band = sell_min >= band_min_price
    band_cap = sell_min * (Decimal("1") + price_band) if apply_band else None

    usable = 0
    order_count = 0
    sell_band_max: Decimal | None = None
    for price, volume in levels:
        if band_cap is not None and price > band_cap:
            break
        usable += volume
        order_count += 1
        sell_band_max = price

    return BandedSellDepth(
        volume=usable,
        volume_total=volume_total,
        order_count=order_count,
        sell_min=sell_min,
        sell_band_max=sell_band_max,
    )


def _fetch_one(
    region_id: int, location_id: int, type_id: int
) -> JitaSellDepth:
    sell_orders: list[tuple[Decimal, int]] = []
    for page in get_region_market_orders_pages(region_id, type_id=type_id):
        if page is None:
            raise RuntimeError(
                f"ESI market orders failed for type_id={type_id}"
            )
        for order in page:
            if order.get("location_id") != location_id:
                continue
            if order.get("is_buy_order"):
                continue
            remain = int(order.get("volume_remain") or 0)
            if remain <= 0:
                continue
            sell_orders.append((Decimal(str(order["price"])), remain))

    banded = compute_banded_sell_depth(sell_orders)
    fetched_at = timezone.now().isoformat()
    depth = JitaSellDepth(
        type_id=type_id,
        volume=banded.volume,
        order_count=banded.order_count,
        sell_min=banded.sell_min,
        fetched_at=fetched_at,
        from_cache=False,
        volume_total=banded.volume_total,
        sell_band_max=banded.sell_band_max,
    )
    cache.set(
        _cache_key(location_id, type_id),
        depth.to_dict(),
        timeout=JITA_DEPTH_CACHE_TTL,
    )
    return depth


def _from_cache(location_id: int, type_id: int) -> JitaSellDepth | None:
    raw = cache.get(_cache_key(location_id, type_id))
    if not raw:
        return None
    sell_min = raw.get("sell_min")
    sell_band_max = raw.get("sell_band_max")
    volume = int(raw["volume"])
    return JitaSellDepth(
        type_id=int(raw["type_id"]),
        volume=volume,
        order_count=int(raw["order_count"]),
        sell_min=Decimal(sell_min) if sell_min is not None else None,
        fetched_at=str(raw["fetched_at"]),
        from_cache=True,
        volume_total=int(raw.get("volume_total", volume)),
        sell_band_max=(
            Decimal(sell_band_max) if sell_band_max is not None else None
        ),
    )


def jita_sell_depth_by_type_id(
    type_ids: Iterable[int],
    *,
    force_refresh: bool = False,
    concurrency: int = DEFAULT_CONCURRENCY,
    on_progress=None,
) -> dict[int, JitaSellDepth]:
    location = baseline_jita_location()
    if location is None:
        raise RuntimeError("No price_baseline EveLocation with region_id set.")

    unique_ids = sorted({int(t) for t in type_ids if t})
    total = len(unique_ids)
    result: dict[int, JitaSellDepth] = {}
    to_fetch: list[int] = []

    for tid in unique_ids:
        if not force_refresh:
            cached = _from_cache(location.location_id, tid)
            if cached is not None:
                result[tid] = cached
                if on_progress:
                    on_progress(len(result), total, cached)
                continue
        to_fetch.append(tid)

    if not to_fetch:
        return result

    workers = max(1, min(concurrency, len(to_fetch)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _fetch_one, location.region_id, location.location_id, tid
            ): tid
            for tid in to_fetch
        }
        for future in as_completed(futures):
            tid = futures[future]
            depth = future.result()
            result[tid] = depth
            if on_progress:
                on_progress(len(result), total, depth)

    return result
