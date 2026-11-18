from django.apps import AppConfig


class TaskboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "taskboard"
    verbose_name = "Tasks"

    def ready(self):
        # pylint: disable-next=import-outside-toplevel
        from taskboard import signals

        signals.connect()
