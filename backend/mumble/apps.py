from django.apps import AppConfig

class MumbleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mumble'

    def ready(self):
        import groups.signals  # pylint: disable=unused-import, import-outside-toplevel