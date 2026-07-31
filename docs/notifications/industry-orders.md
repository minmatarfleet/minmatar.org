# Industry order notifications

First feature wired to the notifications system.

Copy tone: short, plain English, one next step. Written for busy pilots — no jargon, no system-speak.

## Types

| Key | Mechanism | Who | When | Example title |
|-----|-----------|-----|------|---------------|
| `industry.order.created` | Broadcast | Last-30-day participants ∪ topic subscribers ∪ active tribe-group members (excludes creator) | Order created / tribe groups assigned | "New Build Order BTC" |
| `industry.order.assignment` | Action-ack | Assigning user | Self-assign | "You're on the order!" |
| `industry.order.job` | External-event | Assignee | Matched active manufacturing/reaction job | "We've detected an order blueprint cooking!" |

## Audience: new orders

Participation (30 days) includes users who:

- Owned an order (`IndustryOrder.character`)
- Were assigned on an order (via `IndustryOrderItemAssignment`)
- Volunteered as blueprint / mineral / PI coordinator

Plus:

- Anyone with a topic subscription to `industry.order.created`
- **Active members** of any `IndustryOrder.tribe_groups` designated on the order

Helpers: `users_participated_in_orders_since`, `users_active_in_tribe_groups`, `new_order_audience`.

Emit is async (`emit_order_created_notification` Celery task) from order create and again when tribe groups are added (admin M2M). Idempotency key `industry.order.created:{order_id}` prevents duplicate pings when groups are assigned after create.

Discord and Eve mail deliveries are **staggered** under `NOTIFICATIONS_*_RATE_PER_SECOND` (with headroom) so large tribe fans do not slam the rate buckets.

## Assignment payload

Includes order short code, line qty/type, who can help (friendly labels), and hand-in link:

`/industry/orders/contract?order_id=&item_id=&assignment_id=`

## Job matching

On first upsert of an `EveCharacterIndustryJob` during any industry job sync path
(`sync_industry_jobs_for_character` or `update_character`):

1. Job status is `active` or `paused` (not completed)
2. Activity is manufacturing or reaction
3. Character (or same-user alts) has an undelivered assignment on an unfulfilled order
4. Job overlaps the order time window
5. `(blueprint_type_id, activity_id)` produces the line's `eve_type` (`EveIndustryActivityProduct`)

Matching prefers the job's own character over alts, then the most recent claim.

Idempotency: `industry.order.job:{job_id}` so re-syncs do not re-notify.
