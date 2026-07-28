from django.contrib import admin

from notifications.models import (
    NotificationDelivery,
    NotificationPreference,
    NotificationTopicSubscription,
)


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "notification_type",
        "channel",
        "enabled",
        "updated_at",
    )
    list_filter = ("channel", "enabled", "notification_type")
    search_fields = ("user__username", "notification_type")


@admin.register(NotificationTopicSubscription)
class NotificationTopicSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "notification_type", "created_at")
    search_fields = ("user__username", "notification_type")


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "notification_type",
        "channel",
        "status",
        "attempts",
        "created_at",
        "sent_at",
    )
    list_filter = ("channel", "status", "notification_type")
    search_fields = ("user__username", "idempotency_key", "error")
    readonly_fields = ("payload", "created_at", "updated_at", "sent_at")
