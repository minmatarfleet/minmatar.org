from django.apps import AppConfig


class TribesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tribes"

    def ready(self):
        import tribes.signals  # pylint: disable=unused-import, import-outside-toplevel
