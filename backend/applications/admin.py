from django.contrib import admin

from applications.models import (
    AcademyGraduationReview,
    CorporationRequirement,
    EveCorporationApplication,
)


class CorpApplicationAdmin(admin.ModelAdmin):
    """Custom admin model for EveCorporationApplication entities"""

    date_hierarchy = "created_at"
    list_display = [
        "id",
        "created_at",
        "user__username",
        "corporation_id",
        "status",
    ]
    list_filter = ["status"]
    search_fields = ["user__username", "corporation_id"]


admin.site.register(EveCorporationApplication, CorpApplicationAdmin)


@admin.register(CorporationRequirement)
class CorporationRequirementAdmin(admin.ModelAdmin):
    list_display = ("corporation", "kind", "who", "importance", "position")
    list_filter = ("kind", "importance")
    search_fields = ("corporation__name",)
    raw_id_fields = ("corporation", "created_by")


@admin.register(AcademyGraduationReview)
class AcademyGraduationReviewAdmin(admin.ModelAdmin):
    date_hierarchy = "created_at"
    list_display = (
        "user",
        "character_id",
        "decision",
        "reviewed_by",
        "created_at",
    )
    list_filter = ("decision",)
    search_fields = ("user__username", "character_id")
    raw_id_fields = ("user", "reviewed_by")
