# Market pricing

How we store and choose EVE market prices. Agents and developers should use this when implementing appraisals, LP economics, industry costs, or market UI.

## Naming cheat sheet

| Colloquial name | Actual model / API |
|-----------------|--------------------|
| ItemPrice / LocationPrice | `EveMarketItemLocationPrice` |
| Regional / Forge / Jita history / “Jita guide” | `EveMarketItemHistory` via `get_prices_by_type_id` |
| CCP / ESI adjusted average | `eveuniverse.models.EveMarketPrice` |
| Industry “Jita sell” | `jita_sell_prices_by_type_id` (LocationPrice sell → history fallback) |

There is **no** Django model named `ItemPrice`.

## Two different “Jita” concepts

### 1. Jita / Forge **guide** price (preferred for “what is this worth in Jita?”)

Regional daily averages from ESI `GET markets/{region_id}/history/`, stored as `EveMarketItemHistory`.

- Region comes from the single `EveLocation` with `price_baseline=True` (normally Jita → The Forge, region `10000002`).
- Latest day’s `average` is the guide price.
- If history is missing, fall back to `EveMarketPrice.average_price`.

**Helpers (use these):**

- `market.helpers.pricing.get_prices_by_type_id` — shared ISK int map by type ID
- `buyback.helpers.pricing.get_baseline_buy_prices` / `get_baseline_buy_prices_by_name` — Decimal guide for buyback

**Used by:** buyback appraisals, LP store offer economics, ops/markup baselines, sell-order admin “jita_price”, inferred-sale baselines.

**Sync:** Celery `fetch_market_item_history` / `fetch_market_item_history_for_type` → `market.helpers.history`.

### 2. Live **location** order book (“ItemPrice”)

Per-(location, type) aggregates from current ESI orders:

- `sell_price` — lowest sell
- `buy_price` — highest **station-range** buy (region-wide lowballs excluded)
- `split_price` — midpoint when both exist

Stored as `EveMarketItemLocationPrice`.

**Use for:** structure/hub market UIs, comparing local book vs guide, industry sell when a synced baseline sell exists.

**Do not** treat LocationPrice alone as the canonical Jita guide. At the Jita NPC station, buy rows are often empty; using them as “Jita buy” rejected all ore appraisals until buyback switched to history (PR #2548).

**Sync:** `fetch_market_location_prices` for locations with `prices_active=True` (not `market_active`). Jita can sync LocationPrice without enabling alliance market flows.

## Location flags (`EveLocation`)

| Flag | Meaning |
|------|---------|
| `price_baseline` | Exactly one active location. Its **region** drives guide history. |
| `prices_active` | Fetch/update `EveMarketItemLocationPrice` from ESI. |
| `market_active` | Alliance market expectations / sell-order tooling. |

## Decision guide

```
Need a Jita/Forge “guide” or appraisal baseline?
  → get_prices_by_type_id / get_baseline_buy_prices
  → EveMarketItemHistory (+ EveMarketPrice fallback)
  → NOT EveMarketItemLocationPrice alone

Need live sell/buy at Amamake (or another hub)?
  → EveMarketItemLocationPrice for that EveLocation

Need industry planner material “Jita sell”?
  → jita_sell_prices_by_type_id
    (baseline LocationPrice.sell_price, else get_prices_by_type_id)

Only need a coarse average / “has any price”?
  → EveMarketPrice is acceptable; prefer history helpers when building ISK values users see
```

## Correct examples in-repo

- **LP store conversion:** `industry.helpers.lp_store_economics` — baseline `EveMarketItemLocationPrice` sell/buy when present, else Forge history via `get_prices_by_type_id`. **Other cost** = LP-store required items (sell) **plus**, for blueprints, SDE manufacturing materials × offer quantity (Fuzzwork “Materials to build”). Alliance buyback ISK/LP acquisition remains LP-desk only (required items, not BOM). Fuzzwork itself uses a simulated 5% Jita buy (order-book percentile); we use LocationPrice/history, so thin-market rows can still diverge slightly.
- **Buyback:** `buyback.helpers.pricing.get_baseline_buy_prices` — history only; docstring states not live order-book rows.
- **Market admin contrast:** local book from LocationPrice, separate `jita_price` from history/`get_prices_by_type_id`.

## Incorrect pattern (do not repeat)

```python
# Wrong: live station ItemPrice as Jita guide
baseline = EveLocation.objects.get(price_baseline=True)
EveMarketItemLocationPrice.objects.filter(location=baseline).values("buy_price")
```

```python
# Right
from market.helpers.pricing import get_prices_by_type_id
prices = get_prices_by_type_id(type_ids)
```
