# Notifications

Multi-channel, preference-gated notifications for minmatar.org.

## Channels

| Channel | Transport | Sender |
|---------|-----------|--------|
| `web` | Browser Web Push | Backend `pywebpush` + VAPID keys |
| `discord` | Direct message | Discord bot (`DISCORD_BOT_TOKEN`) |
| `eve_mail` | ESI mail | **BearThatCares** (`NOTIFICATIONS_EVE_MAIL_CHARACTER_ID`, default `634915984`) |

Discord **channel** broadcasts (fleet pings, structure alerts, etc.) are outside this system.

## Concepts

- **Registry** — notification types are defined in code (`notifications.registry`), grouped by feature (e.g. `industry`).
- **Channel preferences** — per user × type × channel enablement (`NotificationPreference`). Missing row → type defaults.
- **Topic subscriptions** — for broadcast types only: opt into the *audience* (`NotificationTopicSubscription`), separate from how you receive messages.
- **Delivery** — `notify_users` / `notify_user` create `NotificationDelivery` rows and enqueue Celery `deliver_notification`. Discord and Eve mail are never sent inline in HTTP handlers.
- **Rate limits** — Redis token buckets for Discord DMs and Eve mail (cluster-safe). Celery retries on transient failures.

## Settings

- `NOTIFICATIONS_EVE_MAIL_CHARACTER_ID` (default BearThatCares)
- `NOTIFICATIONS_DISCORD_DM_RATE_PER_SECOND` (default `2`)
- `NOTIFICATIONS_EVE_MAIL_RATE_PER_SECOND` (default `0.5`)
- `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` / `VAPID_CONTACT` (backend send; frontend still needs public key for SW registration)

## APIs

- `GET/PUT /api/notifications/preferences`
- `POST/DELETE /api/notifications/topics/{type_key}`
- `POST /api/notifications/deliveries/{id}/ack` — Mark as read (body: `{ "discord_user_id": <snowflake> }`). Delivery owners or staff/bot service tokens only.

## Discord Mark as read

Discord DMs are sent as **embeds** with an author line for the product area
(e.g. `Industry`), so pilots can tell what kind of ping it is at a glance.
Each DM also includes a **Mark as read** button (`custom_id`: `notif_ack:{delivery_id}`). On click the bot:

1. Calls `POST /api/notifications/deliveries/{id}/ack` with the clicker's Discord snowflake
2. Deletes the DM if ack succeeds

Delivery status becomes `read` and `read_at` is set. Message ids are stored on `NotificationDelivery` when the DM is sent.

## Docs in this folder

- [Adding a notification](adding-a-notification.md)
- [Industry orders](industry-orders.md)
