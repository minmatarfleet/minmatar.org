from django.apps import AppConfig


class EveonlineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "eveonline"

    def ready(self):
        import eveonline.signals  # pylint: disable=unused-import, import-outside-toplevel
        from eveonline.esi_view_patches import (  # pylint: disable=import-outside-toplevel
            patch_esi_receive_callback,
        )

        patch_esi_receive_callback()
