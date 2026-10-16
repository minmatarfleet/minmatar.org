from django.contrib import admin

from recruitment.models import ForumRecruitmentPost


@admin.register(ForumRecruitmentPost)
class ForumRecruitmentPostAdmin(admin.ModelAdmin):
    """Corporation recruitment threads on the EVE Online forums."""

    list_display = ["corporation", "url", "title", "updated_at"]
    search_fields = ["corporation__name", "title", "url"]
    autocomplete_fields = ["corporation"]
    readonly_fields = ["linked_by", "created_at", "updated_at"]
