import logging

from django.contrib import admin, messages
from django.db.models import Sum

from .helpers import recalculate_reimbursement_amount
from .models import (
    EveFleetShipReimbursement,
    ShipReimbursementProgram,
    ShipReimbursementProgramAmount,
)

logger = logging.getLogger(__name__)


@admin.action(description="Recalculate payout for selected SRP requests")
def recalculate_selected_amounts(modeladmin, request, queryset):
    updated = 0
    errors = 0
    for reimbursement in queryset:
        try:
            recalculate_reimbursement_amount(reimbursement)
            updated += 1
        except Exception as exc:
            logger.error(
                "Failed to recalculate SRP request %d: %s",
                reimbursement.pk,
                exc,
            )
            errors += 1
    modeladmin.message_user(
        request,
        f"Recalculated {updated} request(s)."
        + (f" {errors} error(s) — see server logs." if errors else ""),
        messages.SUCCESS if not errors else messages.WARNING,
    )


@admin.action(
    description="Refresh ALL outstanding (pending/approved) SRP requests"
)
def refresh_all_outstanding(modeladmin, request, queryset):
    outstanding = EveFleetShipReimbursement.objects.filter(
        status__in=["pending", "approved"]
    )
    updated = 0
    errors = 0
    for reimbursement in outstanding:
        try:
            recalculate_reimbursement_amount(reimbursement)
            updated += 1
        except Exception as exc:
            logger.error(
                "Failed to recalculate SRP request %d: %s",
                reimbursement.pk,
                exc,
            )
            errors += 1
    modeladmin.message_user(
        request,
        f"Refreshed {updated} outstanding request(s)."
        + (f" {errors} error(s) — see server logs." if errors else ""),
        messages.SUCCESS if not errors else messages.WARNING,
    )


@admin.register(EveFleetShipReimbursement)
class SrpAdmin(admin.ModelAdmin):
    """Admin page for SRP"""

    list_display = (
        "user__username",
        "fleet__created_by__username",
        "character_name",
        "ship_name",
        "killmail_id",
        "status",
        "amount",
    )
    search_fields = ("character_name", "ship_name", "killmail_id")
    list_filter = ["status"]
    actions = [recalculate_selected_amounts, refresh_all_outstanding]

    def changelist_view(self, request, extra_context=None):
        outstanding = EveFleetShipReimbursement.objects.filter(
            status__in=["pending", "approved"]
        )
        agg = outstanding.aggregate(total=Sum("amount"))
        extra_context = extra_context or {}
        extra_context["outstanding_count"] = outstanding.count()
        extra_context["outstanding_total"] = agg["total"] or 0
        return super().changelist_view(request, extra_context=extra_context)


class ProgramAmountInline(admin.TabularInline):
    model = ShipReimbursementProgramAmount
    extra = 0
    readonly_fields = ("created_at", "updated_at")
    fields = ("srp_value", "created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(ShipReimbursementProgram)
class SrpValuesAdmin(admin.ModelAdmin):
    """Admin page for SRP ship values"""

    list_display = (
        "id",
        "eve_type",
        "eve_category_name",
        "current_srp_value",
    )
    search_fields = ["eve_type__name", "=eve_type__id"]
    list_filter = ["eve_type__eve_group__eve_category__name"]
    inlines = [ProgramAmountInline]

    @admin.display(description="EVE Category")
    def eve_category_name(self, obj):
        return obj.eve_type.eve_group.eve_category.name

    @admin.display(description="Current SRP Value")
    def current_srp_value(self, obj):
        latest = obj.amounts.order_by("-created_at", "-id").first()
        return latest.srp_value if latest else None
