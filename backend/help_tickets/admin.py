from django.contrib import admin

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
    list_filter = ("is_active",)
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


@admin.register(HelpTicketPanel)
class HelpTicketPanelAdmin(admin.ModelAdmin):
    list_display = ("channel_id", "message_id", "content_hash")
    readonly_fields = ("content_hash",)

    def has_add_permission(self, request):
        return not HelpTicketPanel.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
