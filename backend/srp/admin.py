import logging

from django.contrib import admin, messages

from .helpers import recalculate_reimbursement_amount
from .models import EveFleetShipReimbursement, ShipReimbursementAmount

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


@admin.register(ShipReimbursementAmount)
class SrpValuesAdmin(admin.ModelAdmin):
    """Admin page for SRP ship values"""

    list_display = (
        "id",
        "kind",
        "name",
        "srp_value",
    )
    search_fields = ["name"]
    list_filter = ["kind"]
