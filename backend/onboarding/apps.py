# pylint: disable=import-outside-toplevel
from django.apps import AppConfig


class OnboardingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "onboarding"

    def ready(self):
        from django.db.models.signals import post_migrate

        from onboarding.seed import ensure_onboarding_programs

        def _ensure(sender, app_config, **kwargs):
            if app_config.label != "onboarding":
                return
            ensure_onboarding_programs()

        post_migrate.connect(
            _ensure,
            dispatch_uid="onboarding.ensure_programs",
        )
