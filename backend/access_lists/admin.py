from django.contrib import admin

from access_lists.models import EveAccessList, EveAccessListMember


class EveAccessListMemberInline(admin.TabularInline):
    model = EveAccessListMember
    extra = 0
    readonly_fields = ("entity_type", "entity_id", "entity_name", "access")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(EveAccessList)
class EveAccessListAdmin(admin.ModelAdmin):
    list_display = (
        "access_list_id",
        "name",
        "owner_character",
        "allow_everyone",
        "member_count",
        "last_synced_at",
    )
    list_filter = ("allow_everyone", "owner_character")
    search_fields = (
        "name",
        "description",
        "access_list_id",
        "owner_character__character_name",
    )
    readonly_fields = (
        "access_list_id",
        "name",
        "description",
        "allow_everyone",
        "owner_character",
        "last_synced_at",
    )
    inlines = [EveAccessListMemberInline]

    @admin.display(description="Members")
    def member_count(self, obj):
        return obj.members.count()


@admin.register(EveAccessListMember)
class EveAccessListMemberAdmin(admin.ModelAdmin):
    list_display = (
        "access_list",
        "entity_type",
        "entity_id",
        "entity_name",
        "access",
    )
    list_filter = ("entity_type", "access", "access_list")
    search_fields = (
        "entity_name",
        "entity_id",
        "access_list__name",
    )
    readonly_fields = (
        "access_list",
        "entity_type",
        "entity_id",
        "entity_name",
        "access",
    )
