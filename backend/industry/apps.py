from django.apps import AppConfig


class IndustryConfig(AppConfig):
    name = "industry"

    def ready(self):
        # pylint: disable=import-outside-toplevel
        from industry.admin import apply_industry_admin_customizations
        import industry.signals  # pylint: disable=unused-import, import-outside-toplevel

        apply_industry_admin_customizations()
