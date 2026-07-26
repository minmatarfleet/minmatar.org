from typing import List, Optional
from datetime import datetime
from django.contrib import admin

from .models import (
    EveFleet,
    EveFleetAudience,
    EveFleetInstance,
    EveFleetInstanceMember,
    EveFleetInstanceMemberImplantSnapshot,
    EveFleetInstanceMemberShipSnapshot,
)

_HIDDEN_FLEETS_INDEX_MODELS = {
    "evefleetinstance",
    "evefleetinstancemember",
    "evefleetinstancememberimplantsnapshot",
    "evefleetinstancemembershipsnapshot",
}


class FleetMemberInline(admin.TabularInline):
    model = EveFleetInstanceMember
    extra = 0
    can_delete = False
    show_change_link = True
    verbose_name = "Pilot"
    verbose_name_plural = "Pilots in this session"
    readonly_fields = (
        "character_name",
        "character_id",
        "role",
        "role_name",
        "ship_name",
        "solar_system_name",
        "join_time",
    )
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


class FleetMemberImplantSnapshotInline(admin.TabularInline):
    model = EveFleetInstanceMemberImplantSnapshot
    extra = 0
    fields = ("implants", "estimated_value_isk", "created_at")
    readonly_fields = ("implants", "estimated_value_isk", "created_at")
    can_delete = False
    show_change_link = True
    max_num = 50
    verbose_name = "Implant snapshot"
    verbose_name_plural = "Implant snapshots"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class FleetMemberShipSnapshotInline(admin.TabularInline):
    model = EveFleetInstanceMemberShipSnapshot
    extra = 0
    fields = (
        "ship_type_id",
        "ship_name",
        "solar_system_id",
        "solar_system_name",
        "created_at",
    )
    readonly_fields = fields
    can_delete = False
    show_change_link = True
    max_num = 50
    verbose_name = "Ship snapshot"
    verbose_name_plural = "Ship snapshots"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class FleetInstanceInline(admin.TabularInline):
    model = EveFleetInstance
    extra = 0
    can_delete = False
    show_change_link = True
    verbose_name = "Tracking session"
    verbose_name_plural = "In-game tracking sessions"
    readonly_fields = (
        "id",
        "start_time",
        "end_time",
        "boss_id",
        "is_free_move",
        "is_registered",
        "last_updated",
    )
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(EveFleetInstance)
class EveFleetInstanceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "eve_fleet",
        "start_time",
        "end_time",
        "boss_id",
        "last_updated",
    )
    list_filter = ("is_registered", "is_free_move")
    search_fields = ("id", "eve_fleet__description", "eve_fleet__objective")
    readonly_fields = (
        "id",
        "eve_fleet",
        "start_time",
        "end_time",
        "is_free_move",
        "is_registered",
        "motd",
        "boss_id",
        "last_updated",
        "created_at",
    )
    inlines = [FleetMemberInline]
    date_hierarchy = "start_time"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EveFleet)
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
    inlines = [FleetInstanceInline]

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


admin.site.register(EveFleetAudience)


@admin.register(EveFleetInstanceMember)
class EveFleetInstanceMemberAdmin(admin.ModelAdmin):
    list_display = (
        "character_name",
        "character_id",
        "eve_fleet_instance",
        "ship_name",
        "solar_system_name",
        "role_name",
        "join_time",
    )
    list_filter = ("role_name",)
    search_fields = ("character_name", "character_id", "ship_name")
    readonly_fields = (
        "eve_fleet_instance",
        "character_id",
        "character_name",
        "join_time",
        "role",
        "role_name",
        "ship_type_id",
        "ship_name",
        "solar_system_id",
        "solar_system_name",
        "squad_id",
        "station_id",
        "takes_fleet_warp",
        "wing_id",
        "created_at",
        "updated_at",
    )
    inlines = [
        FleetMemberImplantSnapshotInline,
        FleetMemberShipSnapshotInline,
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def _filter_fleet_sidebar_models(app_list):
    for app in app_list:
        if app["app_label"] == "fleets" or app.get("name") == "Alliance":
            app["models"] = [
                model
                for model in app["models"]
                if model["object_name"].lower()
                not in _HIDDEN_FLEETS_INDEX_MODELS
            ]
    return app_list


def _fleets_get_app_list(request, app_label=None):
    """Hide fleet instance models from the admin sidebar; manage them on Eve fleets."""
    app_list = fleets_previous_get_app_list(request, app_label)
    return _filter_fleet_sidebar_models(app_list)


fleets_previous_get_app_list = admin.site.get_app_list
admin.site.get_app_list = _fleets_get_app_list
