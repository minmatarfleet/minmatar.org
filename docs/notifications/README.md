# Notifications

Multi-channel, preference-gated notifications for minmatar.org.

## Channels

| Channel | Transport | Sender |
|---------|-----------|--------|
| `web` | Browser Web Push | Backend `pywebpush` + VAPID keys |
| `discord` | Direct message | Discord bot (`DISCORD_BOT_TOKEN`) |
| `eve_mail` | ESI mail | **BearThatCares** (`NOTIFICATIONS_EVE_MAIL_CHARACTER_ID`, default `634915984`) |

Discord **channel** broadcasts (fleet pings, structure alerts, etc.) are outside this system.
They still never run inside a web request; see [Discord outside notifications](#discord-outside-notifications).

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
Each DM also includes a **Mark as read** button (`custom_id`: `notif_ack:{delivery_id}`), unless the payload carries its own `discord_components` (tribe invites). On click the bot:

1. Calls `POST /api/notifications/deliveries/{id}/ack` with the clicker's Discord snowflake
2. Deletes the DM if ack succeeds

Delivery status becomes `read` and `read_at` is set. Message ids are stored on `NotificationDelivery` when the DM is sent.

## Registered types

| Key | Who gets it | Channels (default) |
|-----|-------------|--------------------|
| `industry.*` | Industry order participants | see [Industry orders](industry-orders.md) |
| `fleets.closed` | The FC, when tracking stops | Web (on), Eve mail (on) |
| `tribes.membership_requested` | The tribe group chief, when a pilot applies | Discord (on), Web (off) |
| `tribes.invited` | A pilot a chief invites to a tribe group (Open invite / Decline buttons) | Discord (on), Web (on) |
| `tribes.invite_answered` | The inviter, when the pilot joins or declines | Discord (on), Web (off) |

## Discord outside notifications

Some Discord traffic is not a per-member notification: channel pings, forum
threads, and a few DMs whose sender needs the result straight away or whose
message carries buttons the notification embed cannot. Rules for those:

- **Never call Discord inside a web request.** `DiscordClient` retries rate
  limits with backoff, so one inline call can hold a web worker for minutes.
  Build the message in the handler and queue it with `discord.outbox`
  (`queue_dm`, `queue_channel_message`, or `on_commit_enqueue` for your own
  task). The worker sends it after the transaction commits; failures are
  logged and dropped, as the inline sends were.
- **Person-directed DMs go through `notify_user`** unless there is a reason
  not to. The reviewed exceptions are listed, with reasons, in
  `backend/discord/test_request_path_guard.py` (`SEND_DM_ALLOWLIST`): cyno
  assignments, NPSI action DMs, missing-signup nudges, Reddit CEO DMs,
  external-guild join links and doctrine digests.
- `discord/test_request_path_guard.py` fails if an endpoint, router, view or
  admin module calls Discord directly, or if a new module sends DMs.
- **Error alerts:** `discord.helpers.notify_technology_team(location, detail)`
  is the one helper for posting an error nudge to the technology team. It
  never raises. Log the exception itself first (`logger.exception`) so
  Sentry has the traceback, and alert once per run, not once per item.

## Docs in this folder

- [Adding a notification](adding-a-notification.md)
- [Industry orders](industry-orders.md)
