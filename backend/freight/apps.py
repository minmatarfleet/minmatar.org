from django.apps import AppConfig


class FreightConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "freight"

    def ready(self):
        # Circular import: admin registration must run after apps are ready.
        # pylint: disable=import-outside-toplevel
        from freight.admin import apply_freight_admin_customizations

        apply_freight_admin_customizations()
