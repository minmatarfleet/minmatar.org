from django.apps import AppConfig


class TimezonesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "timezones"
    verbose_name = "Timezones"

    def ready(self):
        # pylint: disable=unused-import, import-outside-toplevel
        import timezones.discord_roles
        import timezones.signals
