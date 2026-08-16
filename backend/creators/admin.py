from django.contrib import admin

from creators.models import CreatorAccount, CreatorItem


@admin.register(CreatorAccount)
class CreatorAccountAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "provider",
        "platform_username",
        "platform_user_id",
        "is_live",
        "token_invalid",
        "last_synced_at",
        "updated_at",
    )
    list_filter = ("provider", "is_live", "token_invalid")
    search_fields = (
        "platform_username",
        "platform_user_id",
        "user__username",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "access_token_preview",
        "refresh_token_preview",
    )
    exclude = ("access_token", "refresh_token")

    @admin.display(description="Access token")
    def access_token_preview(self, obj: CreatorAccount) -> str:
        return _truncate_token(obj.access_token)

    @admin.display(description="Refresh token")
    def refresh_token_preview(self, obj: CreatorAccount) -> str:
        return _truncate_token(obj.refresh_token)


@admin.register(CreatorItem)
class CreatorItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "provider",
        "kind",
        "title",
        "account",
        "published_at",
        "external_id",
    )
    list_filter = ("provider", "kind")
    search_fields = ("title", "external_id", "url")
    raw_id_fields = ("account",)


def _truncate_token(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 12:
        return "***"
    return f"{value[:4]}…{value[-4:]}"
