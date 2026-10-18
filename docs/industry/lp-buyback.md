# LP buyback (Conversion desk)

Pilots sell loyalty points to the alliance, and the Conversion Team buys LP, through orders on the site's buyback board (`/industry/loyalty`). Each order gets a Discord forum thread, and an hourly sweep reminds whoever owes the next step and cancels orders their poster abandoned. This page describes the rules as the code applies them. Price sources for LP store conversion are in [market-pricing.md](../market-pricing.md); this page covers the buyback orders only.

Code: `backend/industry/helpers/lp_market_orders.py` (orders), `backend/industry/helpers/lp_buyback_sweep.py` (timers), `backend/industry/helpers/lp_buyback_discord.py` (threads and pings), `backend/industry/endpoints/loyalty/` (API), `backend/industry/models/lp_store.py` (models).

## Who can do what

| Action | Who | Check |
| --- | --- | --- |
| Post a sell order | Alliance, Militia, Associate by default | `industry.loyalty.trade` feature |
| Post a buy order, claim, move an order along | The LP buyback tribe group (`supply.loyalty-points`) | `industry.loyalty.manage` feature, or `is_staff` (`can_manage_buyback` in `backend/industry/endpoints/loyalty/auth_helpers.py`) |
| Press **LP sent** / **ISK sent** in the Discord thread | The pilot the order is waiting on, or a manager | `post_order_discord_ack.py` |
| Cancel an order | Its poster while it is still `open`; a manager at any status | `patch_order.py` |
| Release a claim | The claimer (their own claims) or a manager (all claims) | `delete_order_claim.py` |

The site's sell desk only trades Tribal Liberation Force LP (`tlf_currency` in `frontend/app/src/helpers/loyalty_order_stats.ts`). The backend accepts any active currency (`IndustryLoyaltyPoint.is_active`) whose `allow_sell` / `allow_buy` flag permits the side.

## Pricing tiers

Each currency (`IndustryLoyaltyPoint`, edited in Django admin) has two published prices:

- **Standard** (`default_isk_per_lp`): the order fills as volume and the market allow. A buy order may name its own ISK/LP; otherwise the standard price is used. The same value prices navy BPCs in the industry planner.
- **Express** (`express_isk_per_lp`): the alliance settles within 24 hours of posting (`EXPRESS_SLA`). Express orders always use the published express price. Leave the field empty to turn express off for that currency.

Every price change is recorded in `IndustryLoyaltyPointPriceHistory` with its tier and the admin who made it.

Sell orders are posted in multiples of `SELL_LP_INCREMENT` (100,000 LP) up to `MAX_SELL_LP` (2,500,000 LP). Buy orders have no cap.

## Order states

`IndustryLoyaltyPointMarketOrder.status` moves only along `ALLOWED_TRANSITIONS`:

```text
open -> claimed -> awaiting_lp -> awaiting_isk -> completed
  any of the first four -> cancelled
```

- **open**: posted, nobody has taken it. Managers can claim all or part of it (`IndustryLoyaltyPointMarketOrderClaim`).
- **claimed**: a claimer has it; the next step is confirming where the LP goes. Moving to `awaiting_lp` needs a destination character.
- **awaiting_lp**: the LP sender owes the LP. On a sell order that is the poster; on a buy order, the claimer.
- **awaiting_isk**: LP has moved; the ISK payer owes ISK. On a sell order that is the claimer; on a buy order, the poster.
- **completed**: a completed sell order posts its ledger entries (`post_sell_order_completion_ledger`).

Every status change stamps `status_changed_at` and clears `stalled_reminder_at`, which is what the timers below read.

## Timers (hourly sweep)

`sweep_lp_buyback_orders_task` runs every hour (at minute 25, `app/settings_celery.py`). Durations are constants in `lp_buyback_sweep.py`:

| Situation | What happens |
| --- | --- |
| The poster owes the next step before LP has moved (`claimed` or `awaiting_lp`, `PRE_LP_STATUSES`) | One reminder in the thread after `REMIND_AFTER` (24 h). Auto-cancel after `AUTO_CANCEL_AFTER` (48 h), and never sooner than 24 h after the reminder (`MIN_WARNING_BEFORE_CANCEL`). The cancel re-checks under a row lock, so pressing **LP sent** during the sweep wins. |
| A claimer owes a step, or ISK is owed (`awaiting_isk`) | Pinged every 24 h. Never cancelled: a slow claimer never costs the poster their order, and cancelling after LP moved would strand the seller. |
| Open for `STALE_OPEN_AFTER` (7 days) with no taker | One weekly digest to the Conversion Team alert channel. |
| An active order has no thread 10 minutes after posting | The thread is created again. |
| A thread is still open for a completed or cancelled order | It is archived. |

Cancelling from the site, Django admin or the sweep posts who cancelled and why in the thread and then archives it (`announce_lp_buyback_cancel_in_thread` in `backend/industry/signals.py`). Deleting an order closes its thread.

## Discord

- Order threads go to the forum channel flagged `receive_lp_buyback` on `DiscordChannel`; the weekly digest goes to the channel flagged `receive_lp_conversion_alerts`. Without a flagged channel the sweep skips that part.
- Status changes are announced after the database commit, from Celery (`notify_lp_buyback_order_status_changed_task`), so a Discord delay never holds a web request.
- The thread buttons (**LP sent**, **ISK sent**) call `POST /api/industry/loyalty/orders/{id}/discord-ack` through the bot.

## Stats

`GET /api/industry/loyalty/stats` (`backend/industry/helpers/lp_order_stats.py`) gives the public buyback page its rolling numbers: by default the last 30 days (`DEFAULT_STATS_DAYS`), split into standard and express, plus 12 weeks of completed LP (`WEEKLY_WEEKS`).

## Admin overrides

Prices, `is_active`, `allow_buy` / `allow_sell` and the express switch are edited on the currency in Django admin. Orders can be edited or cancelled in admin; a cancel there gets the same thread notice as one from the site.
