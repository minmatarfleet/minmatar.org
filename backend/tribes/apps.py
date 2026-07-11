from django.apps import AppConfig


class TribesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tribes"

    def ready(self):
        import tribes.signals  # pylint: disable=unused-import, import-outside-toplevel

        # pylint: disable=import-outside-toplevel
        from tribes.admin import apply_tribes_admin_customizations

        apply_tribes_admin_customizations()
