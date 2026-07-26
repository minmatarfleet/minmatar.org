from django.contrib import admin
from django.urls import path, reverse

from help_tickets.admin_views import (
    help_category_hub_view,
    help_tickets_home_view,
)
from help_tickets.helpers.admin_permissions import (
    help_tickets_index_link_perms,
)
from help_tickets.models import (
    HelpRequestCategory,
    HelpTicket,
    HelpTicketPanel,
)


@admin.register(HelpRequestCategory)
class HelpRequestCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "code",
        "tribe_group",
        "section",
        "sort_order",
        "is_active",
    )
    list_filter = ("is_active", "section")
    search_fields = (
        "title",
        "code",
        "tribe_group__name",
        "tribe_group__tribe__name",
    )
    raw_id_fields = ("tribe_group",)
    filter_horizontal = ("assignees",)
    ordering = ("sort_order", "title")


@admin.register(HelpTicket)
class HelpTicketAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "category",
        "status",
        "thread_name",
        "opener_discord_id",
        "opened_at",
        "closed_at",
    )
    list_filter = ("status", "category")
    search_fields = ("thread_name", "body", "thread_id")
    raw_id_fields = ("category", "opener", "closed_by")
    readonly_fields = ("opened_at",)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        category_id = request.GET.get("category")
        if category_id:
            initial["category"] = int(category_id)
        return initial


@admin.register(HelpTicketPanel)
class HelpTicketPanelAdmin(admin.ModelAdmin):
    list_display = ("channel_id", "message_id", "content_hash")
    readonly_fields = ("content_hash",)

    def has_add_permission(self, request):
        return not HelpTicketPanel.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


HELP_TICKETS_EXTRA_INDEX_LINKS = [
    {
        "name": "Help tickets",
        "admin_url": "admin:help_tickets_home",
    },
]

_HELP_TICKETS_ADMIN_PATCHED_ATTR = "help_tickets_admin_patched"


def _is_help_tickets_admin_model(model: dict) -> bool:
    return model.get("admin_url", "").startswith("/admin/help_tickets/")


def _build_help_tickets_index_link(request) -> dict:
    extra = HELP_TICKETS_EXTRA_INDEX_LINKS[0]
    return {
        "name": extra["name"],
        "object_name": extra["name"],
        "perms": help_tickets_index_link_perms(request.user),
        "admin_url": reverse(extra["admin_url"]),
        "view_only": extra.get("view_only", False),
    }


def _apply_help_tickets_app_list(app_list: list[dict], request) -> list[dict]:
    for app in app_list:
        if app["name"] == "Community":
            models = [
                model
                for model in app["models"]
                if not _is_help_tickets_admin_model(model)
            ]
            models.insert(0, _build_help_tickets_index_link(request))
            app["models"] = models
    return app_list


def _get_custom_help_tickets_admin_urls():
    return [
        path(
            "help-tickets/",
            admin.site.admin_view(help_tickets_home_view),
            name="help_tickets_home",
        ),
        path(
            "help-tickets/category/<int:category_id>/",
            admin.site.admin_view(help_category_hub_view),
            name="help_tickets_category_hub",
        ),
    ]


def apply_help_tickets_admin_customizations():
    """Chain help tickets admin URLs and Community sidebar entry."""
    if getattr(admin.site, _HELP_TICKETS_ADMIN_PATCHED_ATTR, False):
        return

    help_tickets_previous_get_app_list = admin.site.get_app_list

    def _help_tickets_get_app_list(request, app_label=None):
        app_list = help_tickets_previous_get_app_list(request, app_label)
        return _apply_help_tickets_app_list(app_list, request)

    admin.site.get_app_list = _help_tickets_get_app_list

    help_tickets_previous_get_urls = admin.site.get_urls

    def _help_tickets_get_urls():
        return (
            _get_custom_help_tickets_admin_urls()
            + help_tickets_previous_get_urls()
        )

    admin.site.get_urls = _help_tickets_get_urls
    setattr(admin.site, _HELP_TICKETS_ADMIN_PATCHED_ATTR, True)
