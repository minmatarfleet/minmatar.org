# Industry order notifications

First feature wired to the notifications system.

Copy tone: short, plain English, one next step. Written for busy pilots — no jargon, no system-speak.

## Types

| Key | Mechanism | Who | When | Example title |
|-----|-----------|-----|------|---------------|
| `industry.order.created` | Broadcast | Last-30-day participants ∪ topic subscribers (excludes creator) | Order created | "New build order (BTC)" |
| `industry.order.assignment` | Action-ack | Assigning user | Self-assign | "You're building 5× Rifter" |
| `industry.order.job` | External-event | Assignee | Matched manufacturing job | "Rifter is cooking" |

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

On first upsert of an `EveCharacterIndustryJob` during industry job sync:

1. Activity is manufacturing or reaction
2. Character (or same-user alts) has an undelivered assignment on an unfulfilled order
3. Job overlaps the order time window
4. `(blueprint_type_id, activity_id)` produces the line's `eve_type` (`EveIndustryActivityProduct`)

Idempotency: `industry.order.job:{job_id}` so re-syncs do not re-notify.
