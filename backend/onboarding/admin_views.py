"""Custom onboarding admin views."""

from django.urls import reverse

from onboarding.helpers.admin_urls import changelist_url
from onboarding.helpers.admin_views import (
    get_program_or_redirect,
    render_onboarding_view,
)
from onboarding.models import OnboardingProgram, UserOnboardingAcknowledgment


def _program_ack_counts(program: OnboardingProgram) -> dict:
    acks = UserOnboardingAcknowledgment.objects.filter(program=program)
    total = acks.count()
    current = acks.filter(acknowledged_version=program.version).count()
    return {"total": total, "current": current}


def onboarding_home_view(request):
    program_rows = []
    for program in OnboardingProgram.objects.order_by("program_type"):
        counts = _program_ack_counts(program)
        program_rows.append(
            {
                "program": program,
                "ack_total": counts["total"],
                "ack_current": counts["current"],
                "hub_url": reverse(
                    "admin:onboarding_program_hub",
                    args=[program.program_type],
                ),
                "edit_url": reverse(
                    "admin:onboarding_onboardingprogram_change",
                    args=[program.program_type],
                ),
            }
        )
    return render_onboarding_view(
        request,
        title="Onboarding",
        template_name="admin/onboarding/home.html",
        context={
            "program_rows": program_rows,
            "add_program_url": reverse(
                "admin:onboarding_onboardingprogram_add"
            ),
            "all_acks_url": changelist_url("useronboardingacknowledgment"),
        },
    )


def onboarding_program_hub_view(request, program_type):
    program, redirect = get_program_or_redirect(request, program_type)
    if redirect:
        return redirect
    counts = _program_ack_counts(program)
    program_filter = {"program__id__exact": program.program_type}
    return render_onboarding_view(
        request,
        title=f"Onboarding — {program.get_program_type_display()}",
        template_name="admin/onboarding/program_hub.html",
        context={
            "program": program,
            "ack_total": counts["total"],
            "ack_current": counts["current"],
            "sections": {
                "settings": {
                    "edit_url": reverse(
                        "admin:onboarding_onboardingprogram_change",
                        args=[program.program_type],
                    ),
                },
                "acknowledgments": {
                    "total": counts["total"],
                    "current": counts["current"],
                    "list_url": changelist_url(
                        "useronboardingacknowledgment", **program_filter
                    ),
                },
            },
        },
    )
