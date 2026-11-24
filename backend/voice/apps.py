from django.apps import AppConfig


class VoiceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "voice"
    verbose_name = "Fleet voice (Mumble)"

    def ready(self):
        # pylint: disable=import-outside-toplevel,unused-import
        from voice import signals  # noqa: F401
