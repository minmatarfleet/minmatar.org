from django.contrib import admin
from django.urls import path, reverse

from onboarding.admin_views import (
    onboarding_home_view,
    onboarding_program_hub_view,
)
from onboarding.helpers.admin_permissions import onboarding_index_link_perms
from onboarding.models import OnboardingProgram, UserOnboardingAcknowledgment


@admin.register(OnboardingProgram)
class OnboardingProgramAdmin(admin.ModelAdmin):
    list_display = ("program_type", "version")


@admin.register(UserOnboardingAcknowledgment)
class UserOnboardingAcknowledgmentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "program",
        "acknowledged_version",
        "acknowledged_at",
    )
    list_filter = ("program",)
    search_fields = ("user__username",)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        program_id = request.GET.get("program")
        if program_id:
            initial["program"] = program_id
        return initial


ONBOARDING_EXTRA_INDEX_LINKS = [
    {
        "name": "Onboarding",
        "admin_url": "admin:onboarding_home",
    },
]

_ONBOARDING_ADMIN_PATCHED_ATTR = "onboarding_admin_patched"


def _is_onboarding_admin_model(model: dict) -> bool:
    return model.get("admin_url", "").startswith("/admin/onboarding/")


def _build_onboarding_index_link(request) -> dict:
    extra = ONBOARDING_EXTRA_INDEX_LINKS[0]
    return {
        "name": extra["name"],
        "object_name": extra["name"],
        "perms": onboarding_index_link_perms(request.user),
        "admin_url": reverse(extra["admin_url"]),
        "view_only": extra.get("view_only", False),
    }


def _apply_onboarding_app_list(app_list: list[dict], request) -> list[dict]:
    for app in app_list:
        if app["name"] == "System":
            models = [
                model
                for model in app["models"]
                if not _is_onboarding_admin_model(model)
            ]
            models.insert(0, _build_onboarding_index_link(request))
            app["models"] = models
    return app_list


def _get_custom_onboarding_admin_urls():
    return [
        path(
            "onboarding/",
            admin.site.admin_view(onboarding_home_view),
            name="onboarding_home",
        ),
        path(
            "onboarding/program/<str:program_type>/",
            admin.site.admin_view(onboarding_program_hub_view),
            name="onboarding_program_hub",
        ),
    ]


def apply_onboarding_admin_customizations():
    """Chain onboarding admin URLs and System sidebar entry."""
    if getattr(admin.site, _ONBOARDING_ADMIN_PATCHED_ATTR, False):
        return

    onboarding_previous_get_app_list = admin.site.get_app_list

    def _onboarding_get_app_list(request, app_label=None):
        app_list = onboarding_previous_get_app_list(request, app_label)
        return _apply_onboarding_app_list(app_list, request)

    admin.site.get_app_list = _onboarding_get_app_list

    onboarding_previous_get_urls = admin.site.get_urls

    def _onboarding_get_urls():
        return (
            _get_custom_onboarding_admin_urls()
            + onboarding_previous_get_urls()
        )

    admin.site.get_urls = _onboarding_get_urls
    setattr(admin.site, _ONBOARDING_ADMIN_PATCHED_ATTR, True)
