import logging

from django.contrib import admin, messages
from django import forms
from django.db.models import Sum
from django.utils.safestring import mark_safe
from eveuniverse.models import EveType

from .helpers import recalculate_reimbursement_amount
from .models import (
    EveFleetShipReimbursement,
    ShipReimbursementProgram,
    ShipReimbursementProgramAmount,
)

logger = logging.getLogger(__name__)
SHIP_CATEGORY_NAME = "Ship"


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


class ShipReimbursementProgramAdminForm(forms.ModelForm):
    new_srp_value = forms.IntegerField(
        required=False,
        min_value=0,
        help_text="Enter a value and save to append a new price history row.",
        label="New SRP value",
    )

    class Meta:
        model = ShipReimbursementProgram
        fields = "__all__"


class ShipClassFilter(admin.SimpleListFilter):
    title = "Ship class"
    parameter_name = "ship_class"

    def lookups(self, request, model_admin):
        rows = (
            EveType.objects.filter(
                eve_group__eve_category__name=SHIP_CATEGORY_NAME
            )
            .exclude(eve_group__name__isnull=True)
            .values_list("eve_group__name", flat=True)
            .distinct()
            .order_by("eve_group__name")
        )
        return [(name, name) for name in rows if name]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(eve_type__eve_group__name=self.value())
        return queryset


@admin.register(ShipReimbursementProgram)
class SrpValuesAdmin(admin.ModelAdmin):
    """Admin page for SRP ship values"""

    form = ShipReimbursementProgramAdminForm
    list_display = (
        "id",
        "eve_type",
        "ship_class",
        "current_srp_value",
    )
    list_select_related = ("eve_type__eve_group__eve_category",)
    search_fields = ["eve_type__name", "=eve_type__id"]
    autocomplete_fields = ("eve_type",)
    list_filter = [ShipClassFilter]
    readonly_fields = ("current_srp_value", "price_history")
    fields = (
        "eve_type",
        "current_srp_value",
        "new_srp_value",
        "price_history",
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(eve_type__eve_group__eve_category__name=SHIP_CATEGORY_NAME)
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "eve_type":
            kwargs["queryset"] = EveType.objects.filter(
                eve_group__eve_category__name=SHIP_CATEGORY_NAME
            ).select_related("eve_group")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Ship Class")
    def ship_class(self, obj):
        return obj.eve_type.eve_group.name if obj.eve_type_id else ""

    @admin.display(description="Current SRP Value")
    def current_srp_value(self, obj):
        if not obj or not obj.pk:
            return None
        latest = obj.amounts.order_by("-created_at", "-id").first()
        return latest.srp_value if latest else None

    @admin.display(description="Price history")
    def price_history(self, obj):
        if not obj or not obj.pk:
            return "Save program first to see history."
        rows = obj.amounts.order_by("-created_at", "-id")[:25]
        if not rows:
            return "No history yet."
        lines = [
            f"{row.created_at:%Y-%m-%d %H:%M:%S} - {row.srp_value:,} ISK"
            for row in rows
        ]
        return mark_safe("<br>".join(lines))

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        new_srp_value = form.cleaned_data.get("new_srp_value")
        if new_srp_value is not None:
            ShipReimbursementProgramAmount.objects.create(
                program=obj,
                srp_value=new_srp_value,
            )
