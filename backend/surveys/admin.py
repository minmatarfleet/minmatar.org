from django.contrib import admin

from tribes.helpers.executor import executor_user_id

from surveys.models import (
    ExitSurveyAnswer,
    ExitSurveyInvite,
    ExitSurveyResponse,
    SurveyAnswer,
    SurveyCampaign,
    SurveyChangelogEntry,
    SurveyQuestionAggregate,
    SurveyResponse,
)


class SuperuserOnlyAdmin(admin.ModelAdmin):
    """Response data is visible only to superusers, never to staff who merely
    hold the surveys model permission."""

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class ChangelogInline(admin.TabularInline):
    model = SurveyChangelogEntry
    extra = 1


@admin.register(SurveyCampaign)
class SurveyCampaignAdmin(admin.ModelAdmin):
    list_display = ("title", "year", "quarter", "status", "definition_key")
    list_filter = ("status", "year")
    inlines = [ChangelogInline]


class AnswerInline(admin.TabularInline):
    model = SurveyAnswer
    extra = 0
    can_delete = False
    readonly_fields = (
        "question_key",
        "numeric_value",
        "text_value",
        "choice_value",
        "json_value",
    )


@admin.register(SurveyResponse)
class SurveyResponseAdmin(SuperuserOnlyAdmin):
    list_display = (
        "user",
        "campaign",
        "corporation_name",
        "tenure_cohort",
        "activity_tier",
        "submitted_at",
    )
    list_filter = (
        "campaign",
        "corporation_name",
        "tenure_cohort",
        "activity_tier",
    )
    search_fields = ("user__username",)
    readonly_fields = ("submitted_at", "context_snapshot")
    inlines = [AnswerInline]


@admin.register(SurveyChangelogEntry)
class SurveyChangelogEntryAdmin(admin.ModelAdmin):
    list_display = ("heading", "campaign", "published", "sort_order")
    list_filter = ("published", "campaign")


@admin.register(SurveyQuestionAggregate)
class SurveyQuestionAggregateAdmin(SuperuserOnlyAdmin):
    list_display = ("campaign", "question_key", "segment_key", "n", "mean")
    list_filter = ("campaign", "segment_key")
    search_fields = ("question_key",)


def is_executor(request) -> bool:
    """The Alliance Executor's own account (not any superuser)."""
    user_id = executor_user_id()
    return bool(user_id and request.user.pk == user_id)


class ExecutorOnlyAdmin(admin.ModelAdmin):
    """Exit survey data: the Alliance Executor's account only, read only, not
    even other superusers (#3198)."""

    def has_module_permission(self, request):
        return is_executor(request)

    def has_view_permission(self, request, obj=None):
        return is_executor(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ExitAnswerInline(admin.TabularInline):
    model = ExitSurveyAnswer
    extra = 0
    can_delete = False
    readonly_fields = (
        "question_key",
        "numeric_value",
        "choice_value",
        "json_value",
        "text_value",
    )

    def has_view_permission(self, request, obj=None):
        return is_executor(request)


@admin.register(ExitSurveyInvite)
class ExitSurveyInviteAdmin(ExecutorOnlyAdmin):
    list_display = (
        "character_id",
        "definition_key",
        "channel",
        "status",
        "sent_at",
        "responded_at",
    )
    list_filter = ("definition_key", "channel", "status")


@admin.register(ExitSurveyResponse)
class ExitSurveyResponseAdmin(ExecutorOnlyAdmin):
    list_display = (
        "corporation_id",
        "definition_key",
        "definition_version",
        "submitted_at",
    )
    list_filter = ("definition_key", "definition_version")
    inlines = (ExitAnswerInline,)
