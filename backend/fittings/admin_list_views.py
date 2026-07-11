"""Custom fittings/doctrine admin list views."""

from django.contrib import admin
from django.db.models import Count, OuterRef, Subquery
from django.template.response import TemplateResponse
from django.urls import reverse

from eveuniverse.models import EveType

from fittings.helpers.admin_permissions import (
    require_doctrines_admin_view,
    require_fittings_admin_view,
)
from fittings.helpers.fitting_changes import fitting_change_request_tier
from fittings.helpers.permissions import effective_protection_tier
from fittings.models import (
    ChangeRequestStatus,
    EveDoctrine,
    EveDoctrineChangeRequest,
    EveDoctrineFitting,
    EveFitting,
    EveFittingChangeRequest,
)


def _pending_fitting_request_ids() -> set[int]:
    return set(
        EveFittingChangeRequest.objects.filter(
            status=ChangeRequestStatus.PENDING
        ).values_list("fitting_id", flat=True)
    )


def _pending_doctrine_request_ids() -> set[int]:
    return set(
        EveDoctrineChangeRequest.objects.filter(
            status=ChangeRequestStatus.PENDING
        ).values_list("doctrine_id", flat=True)
    )


def fittings_manage_view(request):
    require_fittings_admin_view(request.user)
    pending_ids = _pending_fitting_request_ids()
    ship_sq = EveType.objects.filter(pk=OuterRef("ship_id")).values("name")[:1]
    fittings = EveFitting.objects.annotate(
        _ship_name=Subquery(ship_sq),
        _pod_count=Count("pods", distinct=True),
        _refit_count=Count("refits"),
    ).order_by("name")
    rows = []
    for fitting in fittings:
        tier = fitting_change_request_tier(fitting)
        linked = effective_protection_tier(fitting)
        rows.append(
            {
                "fitting": fitting,
                "ship_name": getattr(fitting, "_ship_name", None) or "—",
                "pod_count": getattr(fitting, "_pod_count", 0),
                "refit_count": getattr(fitting, "_refit_count", 0),
                "protection_tier": (tier if linked else f"{tier} (unlinked)"),
                "has_pending": fitting.pk in pending_ids,
                "edit_url": reverse(
                    "admin:fittings_evefitting_change", args=[fitting.pk]
                ),
            }
        )
    context = {
        **admin.site.each_context(request),
        "title": "Fittings",
        "rows": rows,
        "add_url": reverse("admin:fittings_evefitting_add"),
        "pending_requests_url": reverse(
            "admin:fittings_evefittingchangerequest_changelist"
        ),
        "pending_count": len(pending_ids),
    }
    return TemplateResponse(
        request, "admin/fittings/fittings_list.html", context
    )


def doctrines_manage_view(request):
    require_doctrines_admin_view(request.user)
    pending_ids = _pending_doctrine_request_ids()
    doctrines = EveDoctrine.objects.order_by("name")
    rows = []
    for doctrine in doctrines:
        composition = {
            role: EveDoctrineFitting.objects.filter(
                doctrine=doctrine, role=role
            ).count()
            for role in ("primary", "secondary", "support")
        }
        rows.append(
            {
                "doctrine": doctrine,
                "composition": composition,
                "has_pending": doctrine.pk in pending_ids,
                "edit_url": reverse(
                    "admin:fittings_evedoctrine_change", args=[doctrine.pk]
                ),
            }
        )
    context = {
        **admin.site.each_context(request),
        "title": "Doctrines",
        "rows": rows,
        "add_url": reverse("admin:fittings_evedoctrine_add"),
        "pending_requests_url": reverse(
            "admin:fittings_evedoctrinechangerequest_changelist"
        ),
        "pending_count": len(pending_ids),
    }
    return TemplateResponse(
        request, "admin/fittings/doctrines_list.html", context
    )
