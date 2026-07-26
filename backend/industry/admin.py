from django.contrib import admin
from django.contrib import messages
from django import forms
from django.db.models import Q, Sum
from django.http import HttpResponseRedirect
from django.middleware.csrf import get_token
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from eveuniverse.models import EveGroup

from industry.admin_views import (
    industry_order_hub_view,
    industry_orders_home_view,
)
from industry.forms import (
    IndustryLoyaltyPointAccountAdminForm,
    IndustryLoyaltyPointLedgerEntryAdminForm,
    IndustryOrderAdminForm,
    MiningUpgradeCompletionAdminForm,
)
from industry.helpers.admin_permissions import industry_orders_index_link_perms
from industry.helpers.order_profit_breakdown import (
    ProfitBreakdownRefreshNotAllowed,
    can_refresh_order_profit_breakdown,
    refresh_order_profit_breakdown,
)
from industry.helpers.type_breakdown import get_breakdown_for_industry_product
from industry.helpers.lp_ledger import (
    account_balance,
    remaining_lots,
    resolve_offer_isk_per_lp,
    weighted_average_cost_isk_per_lp,
)
from industry.models import (
    IndustryContractAssociation,
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointAccount,
    IndustryLoyaltyPointContact,
    IndustryLoyaltyPointLedgerEntry,
    IndustryLpStoreOffer,
    IndustryOrder,
    IndustryOrderBlueprintCoordinator,
    IndustryOrderItem,
    IndustryOrderItemAssignment,
    IndustryOrderMineralCoordinator,
    IndustryOrderPiCoordinator,
    IndustryProduct,
    MiningUpgradeCompletion,
)
from tribes.models import TribeGroup


class IndustryLoyaltyPointAccountInline(admin.TabularInline):
    """Edit seller/stockpile holders directly from a loyalty currency."""

    model = IndustryLoyaltyPointAccount
    extra = 0
    show_change_link = True
    fields = (
        "name",
        "role",
        "isk_per_lp",
        "corporation_name",
        "is_active",
        "balance_display",
    )
    readonly_fields = ("balance_display",)
    autocomplete_fields = ("eve_character", "user")

    @admin.display(description="balance")
    def balance_display(self, obj):
        if not obj.pk:
            return "—"
        return f"{account_balance(obj):,}"


class IndustryLoyaltyPointContactInline(admin.TabularInline):
    model = IndustryLoyaltyPointContact
    extra = 1
    show_change_link = True
    autocomplete_fields = ("eve_character", "user")
    fields = (
        "character_name",
        "eve_character",
        "user",
        "discord_username",
        "discord_user_id",
        "is_active",
        "notes",
    )


class IndustryLoyaltyPointLedgerHistoryInline(admin.TabularInline):
    """Read-only lot history. New rows are posted via the account form."""

    model = IndustryLoyaltyPointLedgerEntry
    extra = 0
    can_delete = False
    show_change_link = True
    fields = (
        "created_at",
        "amount_display",
        "isk_per_lp",
        "balance_after",
        "notes",
        "created_by",
    )
    readonly_fields = fields
    ordering = ("-created_at", "-id")

    @admin.display(description="amount")
    def amount_display(self, obj):
        if obj.amount is None:
            return "—"
        sign = "+" if obj.amount > 0 else ""
        return f"{sign}{obj.amount:,}"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class PositiveLpBalanceFilter(admin.SimpleListFilter):
    title = "balance"
    parameter_name = "has_balance"

    def lookups(self, request, model_admin):
        return (
            ("positive", "Positive balance"),
            ("zero", "Zero balance"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == "positive":
            return queryset.annotate(
                _bal=Sum("ledger_entries__amount")
            ).filter(_bal__gt=0)
        if value == "zero":
            return queryset.annotate(
                _bal=Sum("ledger_entries__amount")
            ).filter(Q(_bal__isnull=True) | Q(_bal=0))
        return queryset


@admin.register(IndustryLoyaltyPoint)
class IndustryLoyaltyPointAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "corporation_id",
        "default_isk_per_lp",
        "is_active",
        "account_count",
        "accounts_link",
    )
    list_editable = ("default_isk_per_lp", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "corporation_id")
    inlines = (IndustryLoyaltyPointAccountInline,)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "corporation_id",
                    "default_isk_per_lp",
                    "is_active",
                    "notes",
                ),
                "description": (
                    "Currency catalog for militia / navy LP. Default ISK/LP is "
                    "used by the planner and as the offer fallback for accounts."
                ),
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="accounts")
    def account_count(self, obj):
        return obj.accounts.count()

    @admin.display(description="open accounts")
    def accounts_link(self, obj):
        url = reverse("admin:industry_industryloyaltypointaccount_changelist")
        return format_html(
            '<a href="{}?loyalty_point__id__exact={}">View accounts</a>',
            url,
            obj.pk,
        )


@admin.register(IndustryLoyaltyPointAccount)
class IndustryLoyaltyPointAccountAdmin(admin.ModelAdmin):
    form = IndustryLoyaltyPointAccountAdminForm
    list_display = (
        "name",
        "loyalty_point",
        "role",
        "balance_display",
        "offer_isk_per_lp_display",
        "avg_cost_display",
        "contact_summary",
        "is_active",
    )
    list_filter = (
        "role",
        "is_active",
        "loyalty_point",
        PositiveLpBalanceFilter,
    )
    list_editable = ("role", "is_active")
    search_fields = (
        "name",
        "corporation_name",
        "loyalty_point__name",
        "contacts__character_name",
        "contacts__discord_username",
    )
    autocomplete_fields = ("loyalty_point", "eve_character", "user")
    inlines = (
        IndustryLoyaltyPointContactInline,
        IndustryLoyaltyPointLedgerHistoryInline,
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "loyalty_point",
                    "name",
                    "role",
                    "corporation_name",
                    "eve_character",
                    "user",
                    "is_active",
                    "notes",
                ),
            },
        ),
        (
            "Pricing",
            {
                "fields": ("isk_per_lp",),
                "description": (
                    "Current offer ISK/LP for industrialists (or known seller ask). "
                    "Lot history can still mix 825 / 850 / etc. on the ledger."
                ),
            },
        ),
        (
            "Balance",
            {
                "fields": (
                    "balance_display",
                    "offer_isk_per_lp_display",
                    "avg_cost_display",
                    "lots_display",
                ),
            },
        ),
        (
            "Post ledger entry",
            {
                "fields": (
                    "ledger_direction",
                    "ledger_quantity",
                    "ledger_isk_per_lp",
                    "ledger_notes",
                ),
                "description": (
                    "Leave quantity blank to only update the account. "
                    "To post: choose credit/debit, enter LP quantity and ISK/LP "
                    "for that lot, then Save."
                ),
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )
    readonly_fields = (
        "balance_display",
        "offer_isk_per_lp_display",
        "avg_cost_display",
        "lots_display",
        "created_at",
        "updated_at",
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if obj is None:
            # Balance + ledger post only make sense after the account exists.
            return [
                fs
                for fs in fieldsets
                if fs[0] not in ("Balance", "Post ledger entry")
            ]
        return fieldsets

    def get_inlines(self, request, obj):
        if obj is None:
            return (IndustryLoyaltyPointContactInline,)
        return self.inlines

    @admin.display(description="balance")
    def balance_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        return f"{account_balance(obj):,}"

    @admin.display(description="offer ISK/LP")
    def offer_isk_per_lp_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        return resolve_offer_isk_per_lp(obj)

    @admin.display(description="avg cost")
    def avg_cost_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        avg = weighted_average_cost_isk_per_lp(obj)
        if avg is None:
            return "—"
        return f"{avg:.1f}"

    @admin.display(description="remaining lots")
    def lots_display(self, obj):
        if not obj or not obj.pk:
            return "—"
        lots = remaining_lots(obj)
        if not lots:
            return "—"
        return mark_safe(
            "<br>".join(
                f"{lot.quantity:,} LP @ {lot.isk_per_lp} ISK/LP"
                for lot in lots
            )
        )

    @admin.display(description="contacts")
    def contact_summary(self, obj):
        names = list(
            obj.contacts.filter(is_active=True).values_list(
                "character_name", flat=True
            )[:3]
        )
        if not names:
            return "—"
        suffix = "…" if obj.contacts.filter(is_active=True).count() > 3 else ""
        return ", ".join(names) + suffix

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not isinstance(form, IndustryLoyaltyPointAccountAdminForm):
            return
        try:
            entry = form.post_ledger_if_requested(user=request.user)
        except forms.ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return
        if entry is not None:
            sign = "+" if entry.amount > 0 else ""
            messages.success(
                request,
                f"Posted ledger entry: {sign}{entry.amount:,} LP "
                f"@ {entry.isk_per_lp} ISK/LP (balance {entry.balance_after:,}).",
            )


@admin.register(IndustryLoyaltyPointContact)
class IndustryLoyaltyPointContactAdmin(admin.ModelAdmin):
    list_display = (
        "character_name",
        "account",
        "account_role",
        "loyalty_point_name",
        "discord_username",
        "is_active",
    )
    list_editable = ("is_active",)
    list_filter = ("is_active", "account__loyalty_point", "account__role")
    search_fields = (
        "character_name",
        "discord_username",
        "account__name",
        "account__loyalty_point__name",
    )
    autocomplete_fields = ("account", "eve_character", "user")

    @admin.display(description="role", ordering="account__role")
    def account_role(self, obj):
        return obj.account.get_role_display()

    @admin.display(
        description="loyalty point", ordering="account__loyalty_point__name"
    )
    def loyalty_point_name(self, obj):
        return obj.account.loyalty_point.name


@admin.register(IndustryLoyaltyPointLedgerEntry)
class IndustryLoyaltyPointLedgerEntryAdmin(admin.ModelAdmin):
    form = IndustryLoyaltyPointLedgerEntryAdminForm
    list_display = (
        "created_at",
        "account",
        "amount_display",
        "isk_per_lp",
        "balance_after",
        "notes_short",
        "created_by",
    )
    list_filter = ("account__loyalty_point", "account__role", "account")
    search_fields = ("account__name", "notes")
    autocomplete_fields = ("account",)
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return (
                "account",
                "amount_display",
                "isk_per_lp",
                "balance_after",
                "created_by",
                "created_at",
            )
        return ("balance_after", "created_by", "created_at", "amount_display")

    def get_fieldsets(self, request, obj=None):
        if obj:
            return (
                (
                    None,
                    {
                        "fields": (
                            "account",
                            "amount_display",
                            "isk_per_lp",
                            "balance_after",
                            "notes",
                            "created_by",
                            "created_at",
                        ),
                        "description": (
                            "Amount and ISK/LP are immutable. Edit notes if needed, "
                            "or post a reversing entry from the account page."
                        ),
                    },
                ),
            )
        return (
            (
                None,
                {
                    "fields": (
                        "account",
                        "direction",
                        "quantity",
                        "isk_per_lp",
                        "notes",
                    ),
                    "description": (
                        "Post a credit (LP in) or debit (LP out) against an account. "
                        "Use a distinct ISK/LP per lot when prices differ."
                    ),
                },
            ),
        )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)

        class RequestLedgerForm(form):
            def __init__(self, *args, **inner_kwargs):
                super().__init__(*args, **inner_kwargs)
                self._request_user = request.user

        return RequestLedgerForm

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="amount", ordering="amount")
    def amount_display(self, obj):
        if not obj or obj.amount is None:
            return "—"
        sign = "+" if obj.amount > 0 else ""
        return f"{sign}{obj.amount:,}"

    @admin.display(description="notes")
    def notes_short(self, obj):
        notes = (obj.notes or "").strip()
        if len(notes) <= 48:
            return notes or "—"
        return notes[:45] + "…"


@admin.register(IndustryLpStoreOffer)
class IndustryLpStoreOfferAdmin(admin.ModelAdmin):
    list_display = (
        "offer_id",
        "corporation_id",
        "type_id",
        "lp_cost",
        "isk_cost",
        "quantity",
        "updated_at",
    )
    list_filter = ("corporation_id",)
    search_fields = ("offer_id", "type_id", "corporation_id")
    readonly_fields = (
        "offer_id",
        "corporation_id",
        "type_id",
        "lp_cost",
        "isk_cost",
        "quantity",
        "updated_at",
    )


class IndustryProductEveGroupListFilter(admin.SimpleListFilter):
    """Show only Eve groups that have at least one industry product."""

    title = "type group"
    parameter_name = "eve_group"

    def lookups(self, request, model_admin):
        group_ids = (
            IndustryProduct.objects.filter(
                eve_type__eve_group_id__isnull=False
            )
            .values_list("eve_type__eve_group_id", flat=True)
            .distinct()
            .order_by("eve_type__eve_group_id")
        )
        groups = EveGroup.objects.filter(id__in=group_ids).order_by("name")
        return [(g.id, g.name) for g in groups]

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset
        return queryset.filter(eve_type__eve_group_id=self.value())


class IndustryOrderItemInline(admin.TabularInline):
    """Order items with a link to manage assignments for each item."""

    model = IndustryOrderItem
    extra = 1
    raw_id_fields = ("eve_type",)
    fields = (
        "eve_type",
        "quantity",
        "self_assign_maximum",
        "target_unit_price",
        "target_estimated_margin",
        "assignments_link",
    )
    readonly_fields = ("assignments_link",)

    @admin.display(description="Assignments")
    def assignments_link(self, obj):
        if not obj.pk:
            return "—"
        url = reverse("admin:industry_industryorderitem_change", args=[obj.pk])
        return format_html('<a href="{}">Manage assignments</a>', url)


class IndustryOrderBlueprintCoordinatorInline(admin.TabularInline):
    """Blueprint coordinators volunteering ships on this order."""

    model = IndustryOrderBlueprintCoordinator
    extra = 0
    autocomplete_fields = ("character",)
    raw_id_fields = ("eve_types",)
    readonly_fields = ("created_at",)


class IndustryOrderMineralCoordinatorInline(admin.TabularInline):
    """Mineral coordinators volunteering minerals on this order."""

    model = IndustryOrderMineralCoordinator
    extra = 0
    autocomplete_fields = ("character",)
    raw_id_fields = ("eve_types",)
    readonly_fields = ("created_at",)


class IndustryOrderPiCoordinatorInline(admin.TabularInline):
    """PI coordinators volunteering PI materials on this order."""

    model = IndustryOrderPiCoordinator
    extra = 0
    autocomplete_fields = ("character",)
    raw_id_fields = ("eve_types",)
    readonly_fields = ("created_at",)


@admin.register(IndustryOrder)
class IndustryOrderAdmin(admin.ModelAdmin):
    """Industry orders: manage order items and their assignments from one place."""

    form = IndustryOrderAdminForm
    list_display = (
        "id",
        "public_short_code",
        "created_at",
        "needed_by",
        "fulfilled_at",
        "character",
        "location",
        "items_summary",
    )
    list_filter = ("character", "needed_by")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    autocomplete_fields = ("character", "location", "tribe_groups")
    inlines = [
        IndustryOrderItemInline,
        IndustryOrderBlueprintCoordinatorInline,
        IndustryOrderMineralCoordinatorInline,
        IndustryOrderPiCoordinatorInline,
    ]
    readonly_fields = (
        "created_at",
        "fulfilled_at",
        "mark_fulfilled_button",
        "profit_breakdown_computed_at",
        "refresh_profit_breakdown_button",
        "relevant_jobs_display",
    )
    search_fields = (
        "id",
        "public_short_code",
        "character__character_name",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "character",
                    "location",
                    "tribe_groups",
                    "needed_by",
                    "created_at",
                    "public_short_code",
                    "contract_to",
                ),
            },
        ),
        (
            "Fulfilment",
            {
                "fields": ("fulfilled_at", "mark_fulfilled_button"),
            },
        ),
        (
            "Profit breakdown",
            {
                "fields": (
                    "profit_breakdown_computed_at",
                    "refresh_profit_breakdown_button",
                ),
                "description": (
                    "Stored profit/price snapshot used by order summary "
                    "graphs. Refresh while the order is open, or once if "
                    "no snapshot exists yet."
                ),
            },
        ),
        (
            "Relevant industry jobs",
            {
                "fields": ("relevant_jobs_display",),
                "description": "Jobs from this order's character and assignees "
                "that overlap the order period (in progress or completed).",
            },
        ),
    )

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "tribe_groups":
            kwargs["queryset"] = TribeGroup.objects.filter(
                is_active=True
            ).order_by("tribe__name", "name")
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def changeform_view(
        self, request, object_id=None, form_url="", extra_context=None
    ):
        self._admin_request = request
        return super().changeform_view(
            request, object_id, form_url, extra_context
        )

    def get_urls(self):
        urls = super().get_urls()
        return [
            path(
                "<path:object_id>/mark-fulfilled/",
                self.admin_site.admin_view(self.mark_fulfilled_view),
                name="industry_industryorder_mark_fulfilled",
            ),
            path(
                "<path:object_id>/refresh-profit-breakdown/",
                self.admin_site.admin_view(self.refresh_profit_breakdown_view),
                name="industry_industryorder_refresh_profit_breakdown",
            ),
        ] + urls

    def mark_fulfilled_view(self, request, object_id):
        if not self.has_change_permission(request):
            messages.error(request, "Permission denied.")
            return HttpResponseRedirect("../")
        obj = self.get_object(request, object_id)
        if not obj:
            messages.error(request, "Order not found.")
            return HttpResponseRedirect("../")
        obj.fulfilled_at = timezone.now()
        obj.save(update_fields=["fulfilled_at"])
        messages.success(request, "Order marked as fulfilled.")
        return HttpResponseRedirect(
            reverse("admin:industry_order_hub", args=[obj.pk])
        )

    def refresh_profit_breakdown_view(self, request, object_id):
        if request.method != "POST":
            messages.error(
                request,
                "Refresh profit breakdown requires a POST request.",
            )
            return HttpResponseRedirect(
                reverse("admin:industry_order_hub", args=[object_id])
            )
        if not self.has_change_permission(request):
            messages.error(request, "Permission denied.")
            return HttpResponseRedirect("../")
        obj = self.get_object(request, object_id)
        if not obj:
            messages.error(request, "Order not found.")
            return HttpResponseRedirect("../")
        try:
            refresh_order_profit_breakdown(obj)
        except ProfitBreakdownRefreshNotAllowed as exc:
            messages.error(request, str(exc))
        except Exception as exc:  # noqa: BLE001 — surface planner failures
            messages.error(
                request, f"Failed to refresh profit breakdown: {exc}"
            )
        else:
            messages.success(request, "Order profit breakdown refreshed.")
        return HttpResponseRedirect(
            reverse("admin:industry_order_hub", args=[obj.pk])
        )

    @admin.display(description="Mark as fulfilled")
    def mark_fulfilled_button(self, obj):
        if not obj.pk or obj.fulfilled_at is not None:
            return "—"
        url = reverse(
            "admin:industry_industryorder_mark_fulfilled", args=[obj.pk]
        )
        return format_html(
            '<a class="button" href="{}">Mark order as fulfilled</a>', url
        )

    @admin.display(description="Refresh profit breakdown")
    def refresh_profit_breakdown_button(self, obj):
        if not obj.pk:
            return "—"
        if not can_refresh_order_profit_breakdown(obj):
            return (
                "— (fulfilled orders keep their stored snapshot; "
                "refresh is only available when open or missing)"
            )
        request = getattr(self, "_admin_request", None)
        if request is None:
            return "—"
        url = reverse(
            "admin:industry_industryorder_refresh_profit_breakdown",
            args=[obj.pk],
        )
        return format_html(
            '<form method="post" action="{}">'
            '<input type="hidden" name="csrfmiddlewaretoken" value="{}">'
            '<button type="submit" class="button">Refresh order breakdown</button>'
            "</form>",
            url,
            get_token(request),
        )

    @admin.display(description="Items")
    def items_summary(self, obj):
        if not obj.pk:
            return "—"
        count = obj.items.count()
        return format_html("{} line(s)", count)

    @admin.display(description="Jobs")
    def relevant_jobs_display(self, obj):
        if not obj.pk:
            return "—"
        jobs = obj.relevant_industry_jobs()
        if not jobs:
            return format_html(
                "<p>No industry jobs in this order's period for its character or assignees.</p>"
            )
        rows = []
        for job in jobs:
            rows.append(
                format_html(
                    "<tr>"
                    "<td>{}</td>"
                    "<td>{}</td>"
                    "<td>{}</td>"
                    "<td>{}</td>"
                    "<td>{}</td>"
                    "<td>{}</td>"
                    "<td>{}</td>"
                    "</tr>",
                    job.job_id,
                    job.character.character_name,
                    job.activity_id,
                    job.status,
                    job.runs,
                    (
                        job.start_date.strftime("%Y-%m-%d %H:%M")
                        if job.start_date
                        else "—"
                    ),
                    (
                        job.end_date.strftime("%Y-%m-%d %H:%M")
                        if job.end_date
                        else "—"
                    ),
                )
            )
        table = (
            "<table style='width:100%'>"
            "<thead><tr>"
            "<th>Job ID</th><th>Character</th><th>Activity</th>"
            "<th>Status</th><th>Runs</th><th>Start</th><th>End</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
        )
        return mark_safe(table)


class IndustryOrderItemAssignmentInline(admin.TabularInline):
    model = IndustryOrderItemAssignment
    extra = 0
    autocomplete_fields = ("character",)
    fields = (
        "character",
        "quantity",
        "target_unit_price",
        "target_estimated_margin",
        "has_blueprints",
        "delivered_at",
    )


@admin.register(IndustryOrderItem)
class IndustryOrderItemAdmin(admin.ModelAdmin):
    """Order item detail: manage assignments. Reached via "Manage assignments" on the order."""

    list_display = (
        "order",
        "eve_type",
        "quantity",
        "target_unit_price",
        "target_estimated_margin",
    )
    list_filter = ("order",)
    raw_id_fields = ("eve_type",)
    autocomplete_fields = ("order",)
    inlines = [IndustryOrderItemAssignmentInline]
    search_fields = ("order__id", "eve_type__name")

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        order_id = request.GET.get("order")
        if order_id:
            initial["order"] = order_id
        return initial

    def _redirect_to_order_hub(self, order_id):
        return HttpResponseRedirect(
            reverse("admin:industry_order_hub", args=[order_id])
        )

    def response_add(self, request, obj, post_url_continue=None):
        if obj.order_id:
            return self._redirect_to_order_hub(obj.order_id)
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if obj.order_id:
            return self._redirect_to_order_hub(obj.order_id)
        return super().response_change(request, obj)


@admin.register(IndustryOrderItemAssignment)
class IndustryOrderItemAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "order_item",
        "character",
        "quantity",
        "target_unit_price",
        "target_estimated_margin",
        "has_blueprints",
        "delivered_at",
    )
    list_filter = ("character", "has_blueprints", "order_item__order")
    autocomplete_fields = ("order_item", "character")

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        order_item_id = request.GET.get("order_item")
        if order_item_id:
            initial["order_item"] = order_item_id
        return initial


@admin.register(IndustryOrderBlueprintCoordinator)
class IndustryOrderBlueprintCoordinatorAdmin(admin.ModelAdmin):
    list_display = ("order", "character", "created_at", "eve_types_summary")
    list_filter = ("order", "character")
    autocomplete_fields = ("order", "character")
    raw_id_fields = ("eve_types",)
    readonly_fields = ("created_at",)

    @admin.display(description="Ships")
    def eve_types_summary(self, obj):
        names = list(obj.eve_types.values_list("name", flat=True)[:8])
        if not names:
            return "—"
        suffix = "…" if obj.eve_types.count() > 8 else ""
        return ", ".join(names) + suffix


@admin.register(IndustryOrderMineralCoordinator)
class IndustryOrderMineralCoordinatorAdmin(admin.ModelAdmin):
    list_display = ("order", "character", "created_at", "eve_types_summary")
    list_filter = ("order", "character")
    autocomplete_fields = ("order", "character")
    raw_id_fields = ("eve_types",)
    readonly_fields = ("created_at",)

    @admin.display(description="Minerals")
    def eve_types_summary(self, obj):
        names = list(obj.eve_types.values_list("name", flat=True)[:8])
        if not names:
            return "—"
        suffix = "…" if obj.eve_types.count() > 8 else ""
        return ", ".join(names) + suffix


@admin.register(IndustryOrderPiCoordinator)
class IndustryOrderPiCoordinatorAdmin(admin.ModelAdmin):
    list_display = ("order", "character", "created_at", "eve_types_summary")
    list_filter = ("order", "character")
    autocomplete_fields = ("order", "character")
    raw_id_fields = ("eve_types",)
    readonly_fields = ("created_at",)

    @admin.display(description="PI materials")
    def eve_types_summary(self, obj):
        names = list(obj.eve_types.values_list("name", flat=True)[:8])
        if not names:
            return "—"
        suffix = "…" if obj.eve_types.count() > 8 else ""
        return ", ".join(names) + suffix


@admin.register(IndustryContractAssociation)
class IndustryContractAssociationAdmin(admin.ModelAdmin):
    list_display = (
        "contract_id",
        "order",
        "assignment",
        "score",
        "contract_status",
        "updated_at",
    )
    list_filter = ("contract_status",)
    search_fields = ("contract_id", "order__id", "order__public_short_code")
    raw_id_fields = ("order", "assignment")
    readonly_fields = ("created_at", "updated_at", "signals")
    ordering = ("-score", "-updated_at")


@admin.register(IndustryProduct)
class IndustryProductAdmin(admin.ModelAdmin):
    """Add industry products by selecting an Eve type; breakdown is computed and stored on save."""

    list_display = ("eve_type", "strategy", "volume_display")
    list_filter = ("strategy", IndustryProductEveGroupListFilter)
    raw_id_fields = ("eve_type",)
    search_fields = ("eve_type__name",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "eve_type",
                    "strategy",
                    "blueprint_or_reaction_display",
                ),
            },
        ),
        (
            "Relations (updated on save when produced)",
            {
                "fields": ("supplied_for_display", "supplies_display"),
                "description": "Supplied for = products that use this as a direct component. "
                "Supplies = this product’s direct components. Set strategy=Produced and save to refresh.",
            },
        ),
        (
            "Breakdown",
            {
                "fields": ("breakdown",),
                "description": "Cached nested component tree (root quantity=1). "
                "Computed automatically on save from the Eve type.",
            },
        ),
    )
    readonly_fields = (
        "blueprint_or_reaction_display",
        "supplied_for_display",
        "supplies_display",
    )

    @admin.display(description="Blueprint / reaction type ID")
    def blueprint_or_reaction_display(self, obj):
        if not obj.pk:
            return "—"
        tid = obj.blueprint_or_reaction_type_id
        return tid if tid is not None else "—"

    @admin.display(description="Volume (m³)")
    def volume_display(self, obj):
        if not obj.pk:
            return "—"
        v = obj.volume
        return f"{v:.2f}" if v is not None else "—"

    @admin.display(description="Supplied for")
    def supplied_for_display(self, obj):
        if not obj.pk:
            return "—"
        products = obj.supplied_for.select_related("eve_type").all()[:20]
        if not products:
            return "—"
        return ", ".join(p.eve_type.name for p in products) + (
            " …" if obj.supplied_for.count() > 20 else ""
        )

    @admin.display(description="Direct components (supplies)")
    def supplies_display(self, obj):
        if not obj.pk:
            return "—"
        products = obj.supplies.select_related("eve_type").all()[:20]
        if not products:
            return "—"
        return ", ".join(p.eve_type.name for p in products) + (
            " …" if obj.supplies.count() > 20 else ""
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.eve_type_id:
            try:
                get_breakdown_for_industry_product(
                    obj.eve_type, quantity=1, store=True
                )
                obj.refresh_from_db()
            except Exception:
                pass


@admin.register(MiningUpgradeCompletion)
class MiningUpgradeCompletionAdmin(admin.ModelAdmin):
    form = MiningUpgradeCompletionAdminForm
    list_display = (
        "sov_system",
        "site_name",
        "completed_at",
        "completed_by",
    )
    list_filter = ("sov_system",)
    date_hierarchy = "completed_at"
    ordering = ("-completed_at",)
    raw_id_fields = ("completed_by",)
    search_fields = ("site_name", "sov_system__system_name")
    fields = ("sov_system", "site_name", "completed_at", "completed_by")


INDUSTRY_ORDERS_HIDDEN_MODELS = {
    "industryorder",
    "industryorderitem",
    "industryorderitemassignment",
}

INDUSTRY_SUPPLY_EXCLUDED_MODELS = INDUSTRY_ORDERS_HIDDEN_MODELS | {
    "industryproduct",
    "miningupgradecompletion",
}

INDUSTRY_EXPERIMENTAL_VISIBLE_RENAMES = {
    "industryproduct": "Products",
    "miningupgradecompletion": "Mining completions",
}

INDUSTRY_ORDERS_EXTRA_INDEX_LINKS = [
    {
        "name": "Industry orders",
        "admin_url": "admin:industry_orders_home",
    },
]

_INDUSTRY_ADMIN_PATCHED_ATTR = "industry_admin_patched"


def _build_industry_orders_index_link(request) -> dict:
    extra = INDUSTRY_ORDERS_EXTRA_INDEX_LINKS[0]
    return {
        "name": extra["name"],
        "object_name": extra["name"],
        "perms": industry_orders_index_link_perms(request.user),
        "admin_url": reverse(extra["admin_url"]),
        "view_only": extra.get("view_only", False),
    }


def _rename_industry_experimental_models(models: list[dict]) -> list[dict]:
    renamed = []
    for model in models:
        key = model.get("object_name", "").lower()
        if key in INDUSTRY_EXPERIMENTAL_VISIBLE_RENAMES:
            renamed.append(
                {**model, "name": INDUSTRY_EXPERIMENTAL_VISIBLE_RENAMES[key]}
            )
        else:
            renamed.append(model)
    return renamed


def _apply_industry_app_list(app_list: list[dict], request) -> list[dict]:
    for app in app_list:
        if app["name"] == "Supply":
            models = [
                model
                for model in app["models"]
                if model.get("object_name", "").lower()
                not in INDUSTRY_SUPPLY_EXCLUDED_MODELS
            ]
            models.insert(0, _build_industry_orders_index_link(request))
            app["models"] = models
        elif app["name"] == "Experimental":
            app["models"] = _rename_industry_experimental_models(app["models"])
    return app_list


def _get_custom_industry_admin_urls():
    return [
        path(
            "industry/orders/",
            admin.site.admin_view(industry_orders_home_view),
            name="industry_orders_home",
        ),
        path(
            "industry/order/<int:order_id>/",
            admin.site.admin_view(industry_order_hub_view),
            name="industry_order_hub",
        ),
    ]


def apply_industry_admin_customizations():
    """Chain industry orders hub URLs and Supply sidebar entry."""
    if getattr(admin.site, _INDUSTRY_ADMIN_PATCHED_ATTR, False):
        return

    industry_previous_get_app_list = admin.site.get_app_list

    def _industry_get_app_list(request, app_label=None):
        app_list = industry_previous_get_app_list(request, app_label)
        return _apply_industry_app_list(app_list, request)

    admin.site.get_app_list = _industry_get_app_list

    industry_previous_get_urls = admin.site.get_urls

    def _industry_get_urls():
        return _get_custom_industry_admin_urls() + industry_previous_get_urls()

    admin.site.get_urls = _industry_get_urls
    setattr(admin.site, _INDUSTRY_ADMIN_PATCHED_ATTR, True)
