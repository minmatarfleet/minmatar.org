from django.apps import AppConfig


class CapabilitiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "capabilities"

    def ready(self):
        import capabilities.signals  # pylint: disable=unused-import, import-outside-toplevel
