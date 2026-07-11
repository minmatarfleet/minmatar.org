from django.contrib import admin
from django.urls import path, reverse

from tribes.admin_group_views import tribe_group_hub_view, tribes_view
from tribes.helpers.admin_permissions import tribes_index_link_perms
from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupActivity,
    TribeGroupActivityRecord,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
    TribeGroupMembershipHistory,
    TribeGroupMembershipCharacterHistory,
    TribeGroupRank,
    TribeGroupRequirement,
    TribeGroupRequirementAssetType,
    TribeGroupRequirementSkill,
)


class TribeGroupInline(admin.TabularInline):
    model = TribeGroup
    extra = 0
    fields = ("name", "chief", "is_active", "discord_channel_id")
    show_change_link = True


@admin.register(Tribe)
class TribeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "chief", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    raw_id_fields = ("chief", "group")
    inlines = [TribeGroupInline]


class AssetTypeInline(admin.TabularInline):
    model = TribeGroupRequirementAssetType
    extra = 1
    fields = ("eve_type", "locations")
    autocomplete_fields = ("eve_type",)
    verbose_name = "Qualifying Asset Type"
    verbose_name_plural = (
        "Qualifying Asset Types (any one satisfies the requirement)"
    )


class QualifyingSkillInline(admin.TabularInline):
    model = TribeGroupRequirementSkill
    extra = 1
    fields = ("eve_type", "minimum_level")
    autocomplete_fields = ("eve_type",)
    verbose_name = "Qualifying Skill"
    verbose_name_plural = "Required Skills (character must have ALL of these at their minimum level)"


class TribeGroupRankInline(admin.TabularInline):
    model = TribeGroupRank
    extra = 0
    fields = ("name", "code", "sort_order", "group")
    raw_id_fields = ("group",)


class TribeGroupRequirementInline(admin.TabularInline):
    model = TribeGroupRequirement
    extra = 0
    show_change_link = True
    fields = ()


@admin.register(TribeGroup)
class TribeGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "tribe", "chief", "is_active")
    list_filter = ("is_active", "tribe")
    search_fields = ("name", "code", "tribe__name")
    raw_id_fields = ("tribe", "chief", "group")
    inlines = [TribeGroupRankInline, TribeGroupRequirementInline]

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        tribe_id = request.GET.get("tribe")
        if tribe_id:
            initial["tribe"] = int(tribe_id)
        return initial


@admin.register(TribeGroupRequirement)
class TribeGroupRequirementAdmin(admin.ModelAdmin):
    list_display = ("tribe_group",)
    list_filter = ("tribe_group",)
    raw_id_fields = ("tribe_group",)
    inlines = [AssetTypeInline, QualifyingSkillInline]


class TribeGroupMembershipCharacterInline(admin.TabularInline):
    model = TribeGroupMembershipCharacter
    extra = 0
    fields = ("character",)
    raw_id_fields = ("character",)


class TribeGroupMembershipHistoryInline(admin.TabularInline):
    model = TribeGroupMembershipHistory
    extra = 0
    fields = ("from_status", "to_status", "changed_at", "changed_by", "reason")
    readonly_fields = ("changed_at",)
    raw_id_fields = ("changed_by",)
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(TribeGroupMembership)
class TribeGroupMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "tribe_group",
        "rank",
        "status",
        "created_at",
        "approved_by",
    )
    list_filter = ("status", "tribe_group", "tribe_group__tribe")
    search_fields = ("user__username", "tribe_group__name")
    raw_id_fields = (
        "user",
        "tribe_group",
        "rank",
        "approved_by",
        "removed_by",
    )
    readonly_fields = ("created_at",)
    inlines = [
        TribeGroupMembershipCharacterInline,
        TribeGroupMembershipHistoryInline,
    ]


@admin.register(TribeGroupRank)
class TribeGroupRankAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "tribe_group", "sort_order", "group")
    list_filter = ("tribe_group", "tribe_group__tribe")
    search_fields = ("name", "code", "tribe_group__name")
    raw_id_fields = ("tribe_group", "group")


@admin.register(TribeGroupMembershipCharacter)
class TribeGroupMembershipCharacterAdmin(admin.ModelAdmin):
    list_display = ("character", "membership")
    list_filter = ("membership__tribe_group",)
    search_fields = ("character__character_name",)
    raw_id_fields = ("membership", "character")


@admin.register(TribeGroupMembershipHistory)
class TribeGroupMembershipHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "membership",
        "from_status",
        "to_status",
        "changed_at",
        "changed_by",
        "reason",
    )
    list_filter = ("to_status", "membership__tribe_group")
    search_fields = ("membership__user__username",)
    raw_id_fields = ("membership", "changed_by")
    readonly_fields = ("changed_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class TribeGroupActivityRecordInline(admin.TabularInline):
    model = TribeGroupActivityRecord
    extra = 0
    fields = (
        "character",
        "user",
        "source_type_id",
        "target_type_id",
        "quantity",
        "unit",
        "reference_type",
        "reference_id",
        "created_at",
    )
    readonly_fields = ("created_at",)
    raw_id_fields = ("character", "user")
    show_change_link = True
    can_delete = True
    max_num = 100


@admin.register(TribeGroupActivity)
class TribeGroupActivityAdmin(admin.ModelAdmin):
    list_display = (
        "tribe_group",
        "activity_type",
        "source_eve_type_id",
        "target_eve_type_id",
        "description",
        "is_active",
        "points_per_record",
        "points_per_unit",
        "created_at",
    )
    list_filter = (
        "activity_type",
        "is_active",
        "tribe_group",
        "tribe_group__tribe",
    )
    search_fields = ("tribe_group__name", "description")
    raw_id_fields = ("tribe_group",)
    inlines = [TribeGroupActivityRecordInline]


@admin.register(TribeGroupActivityRecord)
class TribeGroupActivityRecordAdmin(admin.ModelAdmin):
    list_display = (
        "tribe_group_activity",
        "character",
        "user",
        "source_type_id",
        "target_type_id",
        "quantity",
        "unit",
        "reference_type",
        "reference_id",
        "created_at",
    )
    list_filter = (
        "tribe_group_activity__activity_type",
        "tribe_group_activity__tribe_group",
        "reference_type",
    )
    search_fields = ("reference_id", "reference_type")
    raw_id_fields = ("tribe_group_activity", "character", "user")
    readonly_fields = ("created_at",)


@admin.register(TribeGroupMembershipCharacterHistory)
class TribeGroupMembershipCharacterHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "membership",
        "character",
        "action",
        "at",
        "by",
        "leave_reason",
    )
    list_filter = ("action", "leave_reason", "membership__tribe_group")
    search_fields = ("character__character_name",)
    raw_id_fields = ("membership", "character", "by")
    readonly_fields = ("at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


TRIBES_EXTRA_INDEX_LINKS = [
    {
        "name": "Tribes",
        "admin_url": "admin:tribes_home",
    },
]

_TRIBES_ADMIN_PATCHED_ATTR = "tribes_admin_patched"


def _build_tribes_index_models(models: list[dict], request) -> list[dict]:
    index_models = []
    for extra in TRIBES_EXTRA_INDEX_LINKS:
        index_models.append(
            {
                "name": extra["name"],
                "object_name": extra["name"],
                "perms": tribes_index_link_perms(request.user),
                "admin_url": reverse(extra["admin_url"]),
                "view_only": extra.get("view_only", False),
            }
        )
    return index_models


def _is_tribes_admin_model(model: dict) -> bool:
    return model.get("admin_url", "").startswith("/admin/tribes/")


def _apply_tribes_app_list(app_list: list[dict], request) -> list[dict]:
    for app in app_list:
        if app["name"] == "Community":
            models = [
                model
                for model in app["models"]
                if not _is_tribes_admin_model(model)
            ]
            models.extend(_build_tribes_index_models([], request))
            app["models"] = models
    return app_list


def _get_custom_tribes_admin_urls():
    return [
        path(
            "tribes/",
            admin.site.admin_view(tribes_view),
            name="tribes_home",
        ),
        path(
            "tribes/group/<int:group_id>/",
            admin.site.admin_view(tribe_group_hub_view),
            name="tribes_group_hub",
        ),
    ]


def apply_tribes_admin_customizations():
    """Chain tribes admin URLs and sidebar after other app patches."""
    if getattr(admin.site, _TRIBES_ADMIN_PATCHED_ATTR, False):
        return

    tribes_previous_get_app_list = admin.site.get_app_list

    def _tribes_get_app_list(request, app_label=None):
        app_list = tribes_previous_get_app_list(request, app_label)
        return _apply_tribes_app_list(app_list, request)

    admin.site.get_app_list = _tribes_get_app_list

    tribes_previous_get_urls = admin.site.get_urls

    def _tribes_get_urls():
        return _get_custom_tribes_admin_urls() + tribes_previous_get_urls()

    admin.site.get_urls = _tribes_get_urls
    setattr(admin.site, _TRIBES_ADMIN_PATCHED_ATTR, True)
