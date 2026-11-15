from django.contrib import admin

from taskboard.models import (
    Project,
    ProjectStage,
    ProjectTemplate,
    ProjectUpdate,
    Task,
    TaskComment,
    TaskPreferences,
    TaskRuleSetting,
    TemplateTask,
)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "rule", "status", "user", "team_kind")
    list_filter = ("kind", "status", "weight", "rule", "team_kind")
    search_fields = ("title", "source_key", "user__username")
    raw_id_fields = (
        "user",
        "created_by",
        "thanked_by",
        "project",
        "stage",
        "waiting_on",
    )


class TemplateTaskInline(admin.TabularInline):
    model = TemplateTask
    extra = 1


@admin.register(ProjectTemplate)
class ProjectTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "active", "position")
    inlines = [TemplateTaskInline]


class ProjectStageInline(admin.TabularInline):
    model = ProjectStage
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "lead", "status", "target_date")
    list_filter = ("status",)
    raw_id_fields = ("lead", "created_by")
    inlines = [ProjectStageInline]


admin.site.register(ProjectUpdate)
admin.site.register(TaskComment)
admin.site.register(TaskRuleSetting)
admin.site.register(TaskPreferences)
