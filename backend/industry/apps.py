from django.apps import AppConfig


class IndustryConfig(AppConfig):
    name = "industry"

    def ready(self):
        # pylint: disable=import-outside-toplevel
        from industry.admin import apply_industry_admin_customizations

        apply_industry_admin_customizations()
