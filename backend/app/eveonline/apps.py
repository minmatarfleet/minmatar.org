from django.apps import AppConfig


class EveonlineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "eveonline"

    def ready(self):
        import eveonline.signals  # pylint: disable=unused-import, import-outside-toplevel
