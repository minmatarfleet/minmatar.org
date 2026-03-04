from django.contrib import admin

from tribes.models import (
    Tribe,
    TribeGroup,
    TribeGroupMembership,
    TribeGroupMembershipCharacter,
    TribeGroupMembershipHistory,
    TribeGroupMembershipCharacterHistory,
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
    fields = ("eve_type", "minimum_count", "location")
    autocomplete_fields = ("eve_type", "location")
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


class TribeGroupRequirementInline(admin.TabularInline):
    model = TribeGroupRequirement
    extra = 0
    show_change_link = True
    fields = ()


@admin.register(TribeGroup)
class TribeGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "tribe", "chief", "is_active")
    list_filter = ("is_active", "tribe")
    search_fields = ("name", "tribe__name")
    raw_id_fields = ("tribe", "chief", "group")
    inlines = [TribeGroupRequirementInline]


@admin.register(TribeGroupRequirement)
class TribeGroupRequirementAdmin(admin.ModelAdmin):
    list_display = ("tribe_group",)
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
        "status",
        "created_at",
        "approved_by",
    )
    list_filter = ("status", "tribe_group__tribe")
    search_fields = ("user__username", "tribe_group__name")
    raw_id_fields = ("user", "tribe_group", "approved_by", "removed_by")
    readonly_fields = ("created_at",)
    inlines = [
        TribeGroupMembershipCharacterInline,
        TribeGroupMembershipHistoryInline,
    ]


@admin.register(TribeGroupMembershipCharacter)
class TribeGroupMembershipCharacterAdmin(admin.ModelAdmin):
    list_display = ("character", "membership")
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
    list_filter = ("to_status",)
    search_fields = ("membership__user__username",)
    raw_id_fields = ("membership", "changed_by")
    readonly_fields = ("changed_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


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
    list_filter = ("action", "leave_reason")
    search_fields = ("character__character_name",)
    raw_id_fields = ("membership", "character", "by")
    readonly_fields = ("at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
