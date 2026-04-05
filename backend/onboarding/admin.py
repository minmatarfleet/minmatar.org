from django.contrib import admin

from onboarding.models import OnboardingProgram, UserOnboardingAcknowledgment


@admin.register(OnboardingProgram)
class OnboardingProgramAdmin(admin.ModelAdmin):
    list_display = ("program_type", "version")


@admin.register(UserOnboardingAcknowledgment)
class UserOnboardingAcknowledgmentAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "program",
        "acknowledged_version",
        "acknowledged_at",
    )
    list_filter = ("program",)
