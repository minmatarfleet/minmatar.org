from django.contrib import admin

from exits.models import Departure, MemberSnapshot


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
