from datetime import timezone as dt_timezone

from django.contrib import admin
from django.db.models import F, OrderBy
from django.utils import timezone

from .forms import EveStructureTimerForm
from .models import (
    EveStructure,
    EveStructureTimer,
    EveStructurePing,
)


@admin.register(EveStructure)
class EveStructureAdmin(admin.ModelAdmin):
    """Admin page for EveStructure"""

    list_display = (
        "name",
        "system_name",
        "corporation",
        "type_name",
        "reinforced_time_display",
        "fuel_expires_days",
    )
    list_filter = ("type_name", "corporation")
    list_per_page = 50
    search_fields = ("name", "system_name", "corporation__name", "type_name")
    list_display_links = ("name", "system_name")
    readonly_fields = ("id", "system_id", "type_id")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by(OrderBy(F("state_timer_end"), nulls_last=True))

    @admin.display(description="Reinforced time")
    def reinforced_time_display(self, obj):
        if obj.state_timer_end is None:
            return "—"
        dt = obj.state_timer_end
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        utc = dt.astimezone(dt_timezone.utc)
        return f"{utc.strftime('%Y-%m-%d %H:%M')} UTC"

    @admin.display(description="Fuel (days)")
    def fuel_expires_days(self, obj):
        if obj.fuel_expires is None:
            return "—"
        delta = obj.fuel_expires - timezone.now()
        days = delta.days
        if days < 0:
            return "Expired"
        if days == 0:
            return "<1 day"
        return f"{days} day{'s' if days != 1 else ''}"


@admin.register(EveStructureTimer)
class StructureTimerAdmin(admin.ModelAdmin):
    form = EveStructureTimerForm
    list_display = ("name", "state")


@admin.register(EveStructurePing)
class StructurePingAdmin(admin.ModelAdmin):
    """Admin page for structure pings"""

    list_display = (
        "id",
        "notification_id",
        "notification_type",
        "event_time",
        "structure_id",
        "reported_by",
        "discord_success",
    )
