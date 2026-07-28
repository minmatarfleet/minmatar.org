# Adding a notification type

## 1. Register the type

In `backend/notifications/types/` (or import from an app and register in `NotificationsConfig.ready`):

```python
from notifications.models import NotificationChannel
from notifications.registry import NotificationType, register

MY_TYPE = register(
    NotificationType(
        key="feature.event",
        feature="feature",
        label="Human label",
        description="Shown in preferences UI",
        channels=(
            NotificationChannel.WEB,
            NotificationChannel.DISCORD,
            NotificationChannel.EVE_MAIL,
        ),
        defaults={
            NotificationChannel.WEB: True,
            NotificationChannel.DISCORD: False,
            NotificationChannel.EVE_MAIL: False,
        },
        render=render_fn,  # context dict → payload dict
        supports_topic_subscription=False,  # True for broadcast audiences
    )
)
```

`render` should return keys used by channels: `title`, `body`, `url` (web), `discord_message`, `subject`, `eve_mail_body`.

## 2. Pick a mechanism

| Pattern | When | How |
|---------|------|-----|
| **Broadcast** | Many recipients | Build audience (`recent_participants` ∪ `topic_subscribers`) → `notify_users(...)` |
| **Action-ack** | Notify the actor after they do something | `notify_user(request.user, ...)` with next-step context |
| **External-event** | ESI/sync detects something | Match domain object → `notify_user` with stable `idempotency_key` |

Audience helpers live in `notifications.audiences`; domain participation queries stay in the feature app.

## 3. Emit after successful writes

Call emit helpers **after** DB commit / success path. Catch and log exceptions so notifications never fail the primary action.

Use `idempotency_key` for anything that may re-run (Celery sync, retries). Keys are unique per `(idempotency_key, channel)`; fan-out automatically suffixes `:u{user_id}`.

## 4. Channel prerequisites

Deliveries are **skipped** (not failed) when:

- Web: no `UserSubscription` or missing VAPID config
- Discord: no linked `DiscordUser`
- Eve mail: no primary character

## 5. Preferences UI

Registered types appear under `/api/notifications/preferences` automatically. Broadcast types with `supports_topic_subscription=True` also get topic subscribe/unsubscribe endpoints.
