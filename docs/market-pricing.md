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
- `buyback.helpers.pricing.get_baseline_buy_prices` / `get_baseline_buy_prices_by_name` — live Jita buy (then split), Forge history fallback

**Used by:** buyback appraisals, LP store offer economics, ops/markup baselines, sell-order admin “jita_price”, inferred-sale baselines.

**Sync:** Celery `fetch_market_item_history` / `fetch_market_item_history_for_type` → `market.helpers.history`.

### 2. Live **location** order book (“ItemPrice”)

Per-(location, type) aggregates from current ESI orders:

- `sell_price` — lowest sell
- `buy_price` — highest **station-range** buy (region-wide lowballs excluded)
- `split_price` — midpoint when both exist

Stored as `EveMarketItemLocationPrice`.

**Use for:** structure/hub market UIs, comparing local book vs guide, industry sell when a synced baseline sell exists, and buyback Jita buy (via `get_baseline_buy_prices`, which falls back to history when buy/split are empty — PR #2548).

**Sync:** `fetch_market_location_prices` for locations with `prices_active=True` (not `market_active`). Jita can sync LocationPrice without enabling alliance market flows.

## Location flags (`EveLocation`)

| Flag | Meaning |
|------|---------|
| `price_baseline` | Exactly one active location. Its **region** drives guide history. |
| `prices_active` | Fetch/update `EveMarketItemLocationPrice` from ESI. |
| `market_active` | Alliance market expectations / sell-order tooling. |

## Decision guide

```
Need a Jita/Forge “guide” or appraisal baseline (not buyback)?
  → get_prices_by_type_id
  → EveMarketItemHistory (+ EveMarketPrice fallback)
  → NOT EveMarketItemLocationPrice alone

Need buyback “Jita buy”?
  → buyback.helpers.pricing.get_baseline_buy_prices
  → LocationPrice buy, then split, then history

Need live sell/buy at Amamake (or another hub)?
  → EveMarketItemLocationPrice for that EveLocation

Need industry planner material “Jita sell”?
  → jita_sell_prices_by_type_id
    (baseline LocationPrice.sell_price, else get_prices_by_type_id)

Only need a coarse average / “has any price”?
  → EveMarketPrice is acceptable; prefer history helpers when building ISK values users see
```

## Correct examples in-repo

- **LP store conversion:** `industry.helpers.plan_costing.plan_lp_offer_conversion` (via `lp_store_economics`) — baseline `EveMarketItemLocationPrice` sell/buy when present, else Forge history via `get_prices_by_type_id`. **Net ISK/LP** = `(revenue − 3.37% sales tax − input − Red Frog input freight − Red Frog output freight) / LP`, where input = store ISK + required items + Amamake manufacturing (materials, jobs, facility/SCC/reprocessing taxes; **no** alliance route freight; navy BPC LP/ISK stay via `lp_cost` / `isk_cost`). Red Frog freight defaults to **45M ISK per 1.5B** cargo on **Jita ↔ Amo** (3% of required+materials inbound, 3% of revenue outbound). Alliance buyback ISK/LP acquisition remains LP-desk only (required items, not build). Interactive planner / profit / guide use the same `plan_item_cost` API with **alliance hub→facility** freight instead.
- **Buyback:** `buyback.helpers.pricing.get_baseline_buy_prices` — live Jita `buy_price` then `split_price` at the price-baseline location; Forge history if both are missing. Ore pays `min(base compressed buy × variant factor, mineral buy at ore_refine)` then demand/surplus share.
- **Market admin contrast:** local book from LocationPrice, separate `jita_price` from history/`get_prices_by_type_id`.
- **Plan costing:** Prefer `industry.helpers.plan_costing.plan_item_cost` / `cost_build_plan` for all build ISK totals. Freight modes: `off`, `alliance_route`, `value_percent` (Red Frog). Do not call `build_plan_cost_breakdown` from new callers (legacy adapter only).

## Incorrect pattern (do not repeat)

```python
# Wrong: raw LocationPrice as a generic “Jita guide” (use history for that)
baseline = EveLocation.objects.get(price_baseline=True)
EveMarketItemLocationPrice.objects.filter(location=baseline).values("buy_price")

# Right for Forge guide
from market.helpers.pricing import get_prices_by_type_id
prices = get_prices_by_type_id(type_ids)

# Right for buyback Jita buy (live buy/split, history fallback)
from buyback.helpers.pricing import get_baseline_buy_prices
buys = get_baseline_buy_prices(type_ids)
```
