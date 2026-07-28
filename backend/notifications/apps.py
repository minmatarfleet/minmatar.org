from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"
    verbose_name = "Notifications"

    def ready(self):
        # Register built-in notification types (side-effect import).
        # pylint: disable=import-outside-toplevel,unused-import
        from notifications.types import industry  # noqa: F401
