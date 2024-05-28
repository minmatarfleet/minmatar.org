from django.apps import AppConfig


class FleetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "fleets"

    def ready(self):
        import fleets.signals  # pylint: disable=unused-import, import-outside-toplevel
