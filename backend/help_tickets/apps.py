from django.apps import AppConfig


class HelpTicketsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "help_tickets"

    def ready(self):
        from help_tickets.admin import (  # pylint: disable=import-outside-toplevel
            apply_help_tickets_admin_customizations,
        )

        apply_help_tickets_admin_customizations()
