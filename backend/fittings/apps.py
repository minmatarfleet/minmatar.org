from django.apps import AppConfig


class FittingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "fittings"

    def ready(self):
        # pylint: disable=import-outside-toplevel
        from fittings.admin import apply_fittings_admin_customizations

        apply_fittings_admin_customizations()
