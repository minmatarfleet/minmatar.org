from typing import List, Optional
from datetime import datetime
from django.contrib import admin

from .models import (
    EveFleet,
    EveFleetAudience,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetInstanceMemberImplantSnapshot,
)


class FleetMemberInline(admin.TabularInline):
    model = EveFleetInstanceMember


class FleetInstanceInline(admin.TabularInline):
    model = EveFleetInstance
    inlines = [
        FleetMemberInline,
    ]


class FleetAdmin(admin.ModelAdmin):
    """Custom admin model for EveFleet entities"""

    date_hierarchy = "start_time"
    list_display = [
        "start_time",
        "status",
        "objective",
        "description",
        "created_by__username",
    ]
    list_filter = ["status"]
    search_fields = ["description", "objective"]
    readonly_fields = (
        "id",
        "end_time",
        "boss",
        "members",
        "updated",
    )

    def end_time(self, instance) -> Optional[datetime]:
        efi = EveFleetInstance.objects.filter(eve_fleet=instance).first()
        if efi:
            return efi.end_time
        return None

    def boss(self, instance) -> Optional[int]:
        efi = EveFleetInstance.objects.filter(eve_fleet=instance).first()
        if efi:
            return efi.boss_id
        return None

    def updated(self, instance) -> Optional[datetime]:
        efi = EveFleetInstance.objects.filter(eve_fleet=instance).first()
        if efi:
            return efi.last_updated
        return None

    def members(self, instance) -> List[str]:
        members = []
        efi = EveFleetInstance.objects.filter(eve_fleet=instance).first()
        if efi:
            for member in EveFleetInstanceMember.objects.filter(
                eve_fleet_instance=efi
            ):
                members.append(
                    f"{member.character_name} ({member.character_id})"
                )
        return members


admin.site.register(EveFleet, FleetAdmin)
admin.site.register(EveFleetAudience)
admin.site.register(EveFleetInstance)
admin.site.register(EveFleetInstanceMember)


@admin.register(EveFleetInstanceMemberImplantSnapshot)
class EveFleetInstanceMemberImplantSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "member",
        "estimated_value_isk",
        "created_at",
    )
    list_filter = ("created_at",)
    search_fields = (
        "member__character_name",
        "member__character_id",
    )
    readonly_fields = ("implants", "estimated_value_isk", "created_at")
    date_hierarchy = "created_at"
