from django.contrib import admin
from django.db.models import Count, Q

from recruitment.models import (
    ForumRecruitmentPost,
    ScoutOutreach,
    ScoutOutreachClick,
)


@admin.register(ForumRecruitmentPost)
class ForumRecruitmentPostAdmin(admin.ModelAdmin):
    """Corporation recruitment threads on the EVE Online forums."""

    list_display = ["corporation", "url", "title", "updated_at"]
    search_fields = ["corporation__name", "title", "url"]
    autocomplete_fields = ["corporation"]
    readonly_fields = ["linked_by", "created_at", "updated_at"]


class ScoutOutreachClickInline(admin.TabularInline):
    model = ScoutOutreachClick
    extra = 0
    can_delete = False
    fields = ["created_at", "target", "is_bot", "user_agent"]
    readonly_fields = fields
    ordering = ["-created_at"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ScoutOutreach)
class ScoutOutreachAdmin(admin.ModelAdmin):
    """Recruitment scout replies and the clicks on their tracked links."""

    list_display = [
        "code",
        "surface",
        "seat",
        "prospect",
        "visitors",
        "discordvisitor_count",
        "created_at",
    ]
    list_filter = ["surface", "seat"]
    search_fields = ["code", "prospect", "thread_url"]
    readonly_fields = ["code", "created_by", "created_at"]
    inlines = [ScoutOutreachClickInline]

    def get_queryset(self, request):
        human = Q(clicks__is_bot=False)
        return (
            super()
            .get_queryset(request)
            .annotate(
                visitor_count=Count(
                    "clicks__visitor", filter=human, distinct=True
                ),
                discord_count=Count(
                    "clicks__visitor",
                    filter=human & Q(clicks__target="discord"),
                    distinct=True,
                ),
            )
        )

    @admin.display(description="Visitors", ordering="visitor_count")
    def visitors(self, obj):
        return obj.visitor_count

    @admin.display(description="Discord", ordering="discord_count")
    def discordvisitor_count(self, obj):
        return obj.discord_count
