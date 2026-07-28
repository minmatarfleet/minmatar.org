from django.conf import settings
from django.db import models


class NotificationChannel(models.TextChoices):
    WEB = "web", "Web push"
    DISCORD = "discord", "Discord DM"
    EVE_MAIL = "eve_mail", "Eve mail"


class NotificationDeliveryStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class NotificationPreference(models.Model):
    """Per-user channel enablement for a notification type. Missing row = registry default."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    notification_type = models.CharField(max_length=128, db_index=True)
    channel = models.CharField(
        max_length=32, choices=NotificationChannel.choices
    )
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "notification_type", "channel"],
                name="uniq_notification_pref_user_type_channel",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "notification_type"]),
        ]

    def __str__(self):
        state = "on" if self.enabled else "off"
        return (
            f"{self.user_id}:{self.notification_type}:{self.channel}={state}"
        )


class NotificationTopicSubscription(models.Model):
    """
    Explicit opt-in to a broadcast notification type's audience.

    Independent of channel prefs: this gates whether the user is in the
    audience; channel prefs gate how they receive it.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_topic_subscriptions",
    )
    notification_type = models.CharField(max_length=128, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "notification_type"],
                name="uniq_notification_topic_user_type",
            ),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.notification_type}"


class NotificationDelivery(models.Model):
    """Outbound delivery attempt for one user × type × channel."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_deliveries",
    )
    notification_type = models.CharField(max_length=128, db_index=True)
    channel = models.CharField(
        max_length=32, choices=NotificationChannel.choices
    )
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=16,
        choices=NotificationDeliveryStatus.choices,
        default=NotificationDeliveryStatus.PENDING,
        db_index=True,
    )
    error = models.TextField(blank=True, default="")
    attempts = models.PositiveIntegerField(default=0)
    idempotency_key = models.CharField(
        max_length=255, blank=True, null=True, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "channel"]),
            models.Index(
                fields=["idempotency_key", "channel"],
                name="notif_delivery_idem_channel",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_key", "channel"],
                condition=models.Q(idempotency_key__isnull=False)
                & ~models.Q(idempotency_key=""),
                name="uniq_notif_delivery_idem_channel",
            ),
        ]

    def __str__(self):
        return (
            f"{self.notification_type}/{self.channel} → user {self.user_id} "
            f"[{self.status}]"
        )
