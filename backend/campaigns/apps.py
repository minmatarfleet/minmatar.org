from django.apps import AppConfig


class CampaignsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "campaigns"
    verbose_name = "FW Campaigns"

    def ready(self):
        import campaigns.signals  # noqa: F401  # pylint: disable=unused-import, import-outside-toplevel
