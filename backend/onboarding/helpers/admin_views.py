"""Shared helpers for onboarding admin custom views."""

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse

from onboarding.helpers.admin_permissions import require_onboarding_admin_view
from onboarding.models import OnboardingProgram


def get_program_or_redirect(request, program_type):
    program = OnboardingProgram.objects.filter(pk=program_type).first()
    if not program:
        messages.error(request, "Onboarding program not found.")
        return None, HttpResponseRedirect(reverse("admin:index"))
    return program, None


def render_onboarding_view(
    request,
    *,
    title: str,
    template_name: str,
    context: dict,
):
    require_onboarding_admin_view(request.user)
    context = {
        **admin.site.each_context(request),
        "title": title,
        **context,
    }
    return TemplateResponse(request, template_name, context)
