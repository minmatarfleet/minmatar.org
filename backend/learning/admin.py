from django.contrib import admin

from learning.models import (
    Certificate,
    CertificateLearning,
    Learning,
    MentorClass,
    MentorClassTeacher,
    MentorProfile,
    MentorRequest,
    UserCertificateAward,
    UserLearningPreference,
    UserLearningProgress,
)


@admin.register(Learning)
class LearningAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "slug",
        "content_kind",
        "published",
        "estimated_minutes",
        "updated_at",
    )
    list_filter = ("content_kind", "published")
    search_fields = ("title", "slug", "url", "summary")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("title",)


class CertificateLearningInline(admin.TabularInline):
    model = CertificateLearning
    extra = 1
    autocomplete_fields = ("learning",)
    ordering = ("order", "id")


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "slug",
        "published",
        "sort_order",
        "personas_display",
        "updated_at",
    )
    list_filter = ("published",)
    search_fields = ("title", "slug", "summary")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("sort_order", "title")
    inlines = (CertificateLearningInline,)

    @admin.display(description="Personas")
    def personas_display(self, obj: Certificate) -> str:
        personas = obj.personas or []
        return ", ".join(personas) if personas else "—"


@admin.register(UserLearningPreference)
class UserLearningPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "persona",
        "persona_confirmed_at",
        "updated_at",
    )
    list_filter = ("persona",)
    search_fields = ("user__username",)
    readonly_fields = ("user", "persona", "persona_confirmed_at", "updated_at")

    def has_add_permission(self, request):
        return False

    @admin.display(description="Username", ordering="user__username")
    def username(self, obj: UserLearningPreference) -> str:
        return obj.user.username


@admin.register(UserLearningProgress)
class UserLearningProgressAdmin(admin.ModelAdmin):
    list_display = ("username", "learning_title", "completed_at")
    list_filter = ("learning__content_kind",)
    search_fields = ("user__username", "learning__title", "learning__slug")
    readonly_fields = ("user", "learning", "completed_at")

    def has_add_permission(self, request):
        return False

    @admin.display(description="Username", ordering="user__username")
    def username(self, obj: UserLearningProgress) -> str:
        return obj.user.username

    @admin.display(description="Learning", ordering="learning__title")
    def learning_title(self, obj: UserLearningProgress) -> str:
        return obj.learning.title


@admin.register(UserCertificateAward)
class UserCertificateAwardAdmin(admin.ModelAdmin):
    list_display = ("username", "certificate_title", "awarded_at")
    search_fields = (
        "user__username",
        "certificate__title",
        "certificate__slug",
    )
    readonly_fields = ("user", "certificate", "awarded_at")

    def has_add_permission(self, request):
        return False

    @admin.display(description="Username", ordering="user__username")
    def username(self, obj: UserCertificateAward) -> str:
        return obj.user.username

    @admin.display(description="Certificate", ordering="certificate__title")
    def certificate_title(self, obj: UserCertificateAward) -> str:
        return obj.certificate.title


@admin.register(MentorProfile)
class MentorProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "taking_requests", "classes_per_week")
    list_filter = ("status", "taking_requests")
    search_fields = ("user__username",)
    raw_id_fields = ("user", "decided_by")


class MentorClassTeacherInline(admin.TabularInline):
    model = MentorClassTeacher
    extra = 0
    raw_id_fields = ("mentor",)


@admin.register(MentorClass)
class MentorClassAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "status", "minutes", "where", "author")
    list_filter = ("status", "where")
    search_fields = ("title", "slug")
    raw_id_fields = ("author", "learning")
    inlines = (MentorClassTeacherInline,)


@admin.register(MentorRequest)
class MentorRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "pilot",
        "mentor",
        "mentor_class",
        "status",
        "starts_at",
        "pilot_rating",
        "mentor_outcome",
    )
    list_filter = ("status", "pilot_rating", "mentor_outcome")
    search_fields = ("pilot__username", "mentor__user__username")
    raw_id_fields = (
        "pilot",
        "mentor",
        "mentor_class",
        "passed_from",
        "cancelled_by",
    )
