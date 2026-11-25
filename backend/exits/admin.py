from django.contrib import admin, messages

from exits.helpers.answers import AnswerError, clear_flag
from exits.models import Departure, MemberSnapshot, RejoinFlag


class ReadOnlyAdmin(admin.ModelAdmin):
    """Rows are written by the member sync and the CEO; the admin only shows them."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MemberSnapshot)
class MemberSnapshotAdmin(ReadOnlyAdmin):
    list_display = ("corporation", "alliance_id", "taken_at")


@admin.register(Departure)
class DepartureAdmin(ReadOnlyAdmin):
    list_display = (
        "character_id",
        "corporation",
        "status",
        "kind",
        "reason",
        "can_rejoin",
        "first_missing_at",
    )
    list_filter = ("status", "kind", "reason")
    search_fields = ("character_id", "corporation__name")


@admin.register(RejoinFlag)
class RejoinFlagAdmin(ReadOnlyAdmin):
    list_display = (
        "character_id",
        "corporation",
        "set_by",
        "set_at",
        "note",
        "is_active",
    )
    list_filter = ("cleared_at",)
    search_fields = ("character_id", "corporation__name", "note")
    actions = ("clear_flags",)

    @admin.display(boolean=True, description="Active")
    def is_active(self, obj):
        return obj.active

    @admin.action(description="Clear the selected flags")
    def clear_flags(self, request, queryset):
        cleared = 0
        for flag in queryset.filter(cleared_at__isnull=True):
            try:
                clear_flag(request.user, flag)
                cleared += 1
            except AnswerError as error:
                self.message_user(request, error.message, messages.ERROR)
        self.message_user(request, f"Cleared {cleared} flag(s)")
