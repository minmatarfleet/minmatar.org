# Industry order notifications

First feature wired to the notifications system.

Copy tone: short, plain English, one next step. Written for busy pilots — no jargon, no system-speak.

## Types

| Key | Mechanism | Who | When | Example title |
|-----|-----------|-----|------|---------------|
| `industry.order.created` | Broadcast | Last-30-day participants ∪ topic subscribers (excludes creator) | Order created | "New Build Order BTC" |
| `industry.order.assignment` | Action-ack | Assigning user | Self-assign | "You're on the order!" |
| `industry.order.job` | External-event | Assignee | Matched active manufacturing/reaction job | "We've detected an order blueprint cooking!" |

## Audience: new orders

Participation (30 days) includes users who:

- Owned an order (`IndustryOrder.character`)
- Were assigned on an order (via `IndustryOrderItemAssignment`)
- Volunteered as blueprint / mineral / PI coordinator

Plus anyone with a topic subscription to `industry.order.created`.

Helpers: `industry.helpers.notifications.users_participated_in_orders_since`, `new_order_audience`.

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
