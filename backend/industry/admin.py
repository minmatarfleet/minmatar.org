import logging

from django.contrib import admin
from django.contrib import messages
from django import forms
from django.core.cache import cache
from django.db.models import Count, Max, Q, Sum
from django.http import HttpResponseRedirect
from django.middleware.csrf import get_token
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from market.models.history import EveMarketItemHistory

from eveuniverse.models import EveGroup, EveType

from industry.admin_views import (
    industry_loyalty_home_view,
    industry_order_hub_view,
    industry_orders_home_view,
)
from industry import admin_lp_market_order  # pylint: disable=unused-import
from industry.forms import (
    IndustryLoyaltyPointAccountAdminForm,
    IndustryLoyaltyPointLedgerEntryAdminForm,
    IndustryOrderAdminForm,
    MiningUpgradeCompletionAdminForm,
)
from industry.helpers.admin_permissions import (
    industry_orders_index_link_perms,
    loyalty_index_link_perms,
)
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
from industry.helpers.lp_catalog import (
    chip_type_ids,
    supply_package_type_ids,
    tag_type_ids,
)
from industry.helpers.lp_store_economics import (
    annotate_lp_store_offer_sort_fields,
    offer_economics_for_queryset,
    offer_pks_below_set_lp_price,
    tracked_corporation_ids,
)
from industry.helpers.lp_store_useless import useless_offer_pks
from industry.tasks import (
    compute_order_profit_breakdown_task,
    sync_loyalty_store_offers_task,
)
from industry.models import (
    IndustryContractAssociation,
    IndustryLoyaltyPoint,
    IndustryLoyaltyPointAccount,
    IndustryLoyaltyPointContact,
    IndustryLoyaltyPointLedgerEntry,
    IndustryLoyaltyPointPriceHistory,
    IndustryLpStoreOffer,
    IndustryLpStoreOfferRequiredItem,
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

logger = logging.getLogger(__name__)

# Request attribute for one shared tracked-catalog economics map per
# changelist (filters + list_display stash). Avoids N× full recomputes.
_LP_OFFER_ECON_ATTR = "_lp_offer_econ"
# Short-lived cross-request cache so toggling filters does not recompute
# ~1.5k offers every time. Invalidates when offer/currency/history inputs
# change; TTL bounds LocationPrice / planner staleness.
_LP_OFFER_ECON_CACHE_PREFIX = "industry:lp_offer_econ:v1"
_LP_OFFER_ECON_CACHE_TTL = 180
_LP_ECON_FILTER_PARAMS = (
    "exclude_useless_offers",
    "exclude_below_set_lp_price",
)


def _lp_econ_filters_active(request) -> bool:
    params = getattr(request, "GET", {})
    return any(
        params.get(name) in ("0", "1") for name in _LP_ECON_FILTER_PARAMS
    )


def lp_offer_econ_cache_key() -> str:
    """
    Cache key for the full tracked-catalog economics map.

    Fingerprint includes tracked corps, offer count + max(updated_at),
    active currency default_isk_per_lp rates, and max Forge history date
    so offer sync / buyback edits / daily history refresh invalidate.
    """
    corp_ids = tracked_corporation_ids()
    corp_key = ",".join(str(c) for c in sorted(corp_ids)) or "none"
    if corp_ids:
        offer_stats = IndustryLpStoreOffer.objects.filter(
            corporation_id__in=corp_ids
        ).aggregate(n=Count("pk"), max_u=Max("updated_at"))
    else:
        offer_stats = {"n": 0, "max_u": None}
    currency_fp = (
        ",".join(
            f"{row.corporation_id}:{row.default_isk_per_lp}"
            for row in IndustryLoyaltyPoint.objects.filter(
                is_active=True
            ).order_by("corporation_id")
        )
        or "none"
    )
    hist_max = EveMarketItemHistory.objects.aggregate(m=Max("date"))["m"]
    n = int(offer_stats["n"] or 0)
    max_u = offer_stats["max_u"]
    max_u_s = max_u.isoformat() if max_u is not None else "none"
    hist_s = hist_max.isoformat() if hist_max is not None else "none"
    return (
        f"{_LP_OFFER_ECON_CACHE_PREFIX}:{corp_key}|n={n}|u={max_u_s}"
        f"|lp={currency_fp}|h={hist_s}"
    )


def ensure_lp_offer_econ_on_request(request):
    """
    Resolve economics for all tracked LP store offers.

    Lookup order: request stash → Django cache → compute. Filters and
    list_display share the request-scoped map; the cross-request cache
    avoids recomputing when operators re-toggle exclude filters.
    """
    cached = getattr(request, _LP_OFFER_ECON_ATTR, None)
    if cached is not None:
        return cached
    cache_key = lp_offer_econ_cache_key()
    economics = cache.get(cache_key)
    if economics is not None:
        setattr(request, _LP_OFFER_ECON_ATTR, economics)
        return economics
    offers = list(
        IndustryLpStoreOffer.objects.filter(
            corporation_id__in=tracked_corporation_ids()
        )
    )
    economics = offer_economics_for_queryset(offers)
    setattr(request, _LP_OFFER_ECON_ATTR, economics)
    cache.set(cache_key, economics, timeout=_LP_OFFER_ECON_CACHE_TTL)
    return economics


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
        "market_order",
        "seller_character_name",
        "counterparty_character_name",
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


class IndustryLoyaltyPointPriceHistoryInline(admin.TabularInline):
    """Read-only ISK/LP price changes for a currency (defaults + account offers)."""

    model = IndustryLoyaltyPointPriceHistory
    fk_name = "loyalty_point"
    extra = 0
    can_delete = False
    show_change_link = False
    fields = (
        "changed_at",
        "account",
        "old_isk_per_lp",
        "new_isk_per_lp",
        "changed_by",
    )
    readonly_fields = fields
    ordering = ("-changed_at", "-id")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class IndustryLoyaltyPointAccountPriceHistoryInline(admin.TabularInline):
    """Read-only offer price changes for one account."""

    model = IndustryLoyaltyPointPriceHistory
    fk_name = "account"
    extra = 0
    can_delete = False
    show_change_link = False
    fields = (
        "changed_at",
        "old_isk_per_lp",
        "new_isk_per_lp",
        "changed_by",
    )
    readonly_fields = fields
    ordering = ("-changed_at", "-id")

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
    inlines = (
        IndustryLoyaltyPointAccountInline,
        IndustryLoyaltyPointPriceHistoryInline,
    )
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

    def save_model(self, request, obj, form, change):
        obj.history_changed_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        if formset.model is IndustryLoyaltyPointAccount:
            instances = formset.save(commit=False)
            for obj in instances:
                obj.history_changed_by = request.user
                obj.save()
            formset.save_m2m()
            for obj in formset.deleted_objects:
                obj.delete()
            return
        super().save_formset(request, form, formset, change)

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
        IndustryLoyaltyPointAccountPriceHistoryInline,
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
        obj.history_changed_by = request.user
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


@admin.register(IndustryLoyaltyPointPriceHistory)
class IndustryLoyaltyPointPriceHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "changed_at",
        "loyalty_point",
        "account",
        "old_isk_per_lp",
        "new_isk_per_lp",
        "changed_by",
    )
    list_filter = ("loyalty_point",)
    list_select_related = ("loyalty_point", "account", "changed_by")
    search_fields = (
        "loyalty_point__name",
        "account__name",
        "changed_by__username",
    )
    readonly_fields = (
        "loyalty_point",
        "account",
        "old_isk_per_lp",
        "new_isk_per_lp",
        "changed_at",
        "changed_by",
    )
    ordering = ("-changed_at", "-id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


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
        "market_order_link",
        "seller_character_name",
        "counterparty_character_name",
        "notes_short",
        "created_by",
    )
    list_filter = (
        "account__loyalty_point",
        "account__role",
        "account",
        ("market_order", admin.EmptyFieldListFilter),
    )
    search_fields = (
        "account__name",
        "notes",
        "seller_character_name",
        "counterparty_character_name",
    )
    autocomplete_fields = ("account", "market_order")
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return (
                "account",
                "amount_display",
                "isk_per_lp",
                "balance_after",
                "market_order",
                "market_order_link",
                "seller_user",
                "seller_character_name",
                "counterparty_user",
                "counterparty_character_name",
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
                (
                    "Buyback counterparties",
                    {
                        "fields": (
                            "market_order",
                            "seller_user",
                            "seller_character_name",
                            "counterparty_user",
                            "counterparty_character_name",
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

    def save_model(self, request, obj, form, change):
        if not change:
            # Already persisted by form.save() via post_ledger_entry.
            return
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="amount", ordering="amount")
    def amount_display(self, obj):
        if not obj or obj.amount is None:
            return "—"
        sign = "+" if obj.amount > 0 else ""
        return f"{sign}{obj.amount:,}"

    @admin.display(description="market order", ordering="market_order")
    def market_order_link(self, obj):
        if not obj or not obj.market_order_id:
            return "—"
        url = reverse(
            "admin:industry_industryloyaltypointmarketorder_change",
            args=[obj.market_order_id],
        )
        return format_html('<a href="{}">#{}</a>', url, obj.market_order_id)

    @admin.display(description="notes")
    def notes_short(self, obj):
        notes = (obj.notes or "").strip()
        if len(notes) <= 48:
            return notes or "—"
        return notes[:45] + "…"


class IndustryLpStoreCurrencyListFilter(admin.SimpleListFilter):
    title = "currency"
    parameter_name = "currency"

    def lookups(self, request, model_admin):
        rows = IndustryLoyaltyPoint.objects.filter(is_active=True).order_by(
            "name"
        )
        return [(str(r.corporation_id), r.name) for r in rows]

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset
        return queryset.filter(corporation_id=int(self.value()))


class IndustryLpStoreExcludeTagsFilter(admin.SimpleListFilter):
    title = "exclude tags"
    parameter_name = "exclude_tags"

    def lookups(self, request, model_admin):
        return (("1", "Yes"), ("0", "No"))

    def queryset(self, request, queryset):
        value = self.value()
        if value not in ("0", "1"):
            return queryset
        tag_ids = tag_type_ids()
        if not tag_ids:
            return queryset
        # Offers that *are* tags or that require a tag as input.
        req_offer_ids = IndustryLpStoreOfferRequiredItem.objects.filter(
            type_id__in=tag_ids
        ).values("offer_id")
        tag_q = Q(type_id__in=tag_ids) | Q(pk__in=req_offer_ids)
        if value == "1":
            return queryset.exclude(tag_q)
        return queryset.filter(tag_q)


class IndustryLpStoreExcludeSupplyPackagesFilter(admin.SimpleListFilter):
    title = "exclude supply packages"
    parameter_name = "exclude_supply_packages"

    def lookups(self, request, model_admin):
        return (("1", "Yes"), ("0", "No"))

    def queryset(self, request, queryset):
        value = self.value()
        if value not in ("0", "1"):
            return queryset
        package_ids = supply_package_type_ids()
        if not package_ids:
            return queryset
        # Offers that *are* supply packages or require one as input.
        req_offer_ids = IndustryLpStoreOfferRequiredItem.objects.filter(
            type_id__in=package_ids
        ).values("offer_id")
        package_q = Q(type_id__in=package_ids) | Q(pk__in=req_offer_ids)
        if value == "1":
            return queryset.exclude(package_q)
        return queryset.filter(package_q)


class IndustryLpStoreExcludeChipsFilter(admin.SimpleListFilter):
    title = "exclude chips"
    parameter_name = "exclude_chips"

    def lookups(self, request, model_admin):
        return (("1", "Yes"), ("0", "No"))

    def queryset(self, request, queryset):
        value = self.value()
        if value not in ("0", "1"):
            return queryset
        chip_ids = chip_type_ids()
        if not chip_ids:
            return queryset
        # Offers that *are* nexus chips or require one as input.
        req_offer_ids = IndustryLpStoreOfferRequiredItem.objects.filter(
            type_id__in=chip_ids
        ).values("offer_id")
        chip_q = Q(type_id__in=chip_ids) | Q(pk__in=req_offer_ids)
        if value == "1":
            return queryset.exclude(chip_q)
        return queryset.filter(chip_q)


class IndustryLpStoreExcludeUselessOffersFilter(admin.SimpleListFilter):
    """
    Hide (or isolate) offers that are useless for LP conversion screening.

    Yes = hide useless; No = show only useless. Uses offer_is_useless:
    stockpile usefulness, profit vs buyback, below peer median, and
    volume/volatility (Forge 30d + spread proxy). See
    industry.helpers.lp_store_useless.

    Economics come from ensure_lp_offer_econ_on_request (shared with the
    below-set filter and list_display stash for this request).
    """

    title = "exclude useless offers"
    parameter_name = "exclude_useless_offers"

    def lookups(self, request, model_admin):
        return (("1", "Yes"), ("0", "No"))

    def queryset(self, request, queryset):
        value = self.value()
        if value not in ("0", "1"):
            return queryset
        economics = ensure_lp_offer_econ_on_request(request)
        useless = useless_offer_pks(queryset, economics=economics)
        if value == "1":
            return queryset.exclude(pk__in=useless)
        return queryset.filter(pk__in=useless)


class IndustryLpStoreExcludeBelowSetLpPriceFilter(admin.SimpleListFilter):
    """
    Hide (or isolate) offers whose ISK/LP sell is below set buyback.

    Compares conversion_isk_per_lp_sell to IndustryLoyaltyPoint
    default_isk_per_lp for the offer's corporation. Null conversion
    counts as below set (missing prices → cannot beat buyback).

    Reuses request-scoped catalog economics from
    ensure_lp_offer_econ_on_request when already warmed.
    """

    title = "exclude below set LP price"
    parameter_name = "exclude_below_set_lp_price"

    def lookups(self, request, model_admin):
        return (("1", "Yes"), ("0", "No"))

    def queryset(self, request, queryset):
        value = self.value()
        if value not in ("0", "1"):
            return queryset
        economics = ensure_lp_offer_econ_on_request(request)
        below = offer_pks_below_set_lp_price(queryset, economics=economics)
        if value == "1":
            return queryset.exclude(pk__in=below)
        return queryset.filter(pk__in=below)


@admin.register(IndustryLpStoreOffer)
class IndustryLpStoreOfferAdmin(admin.ModelAdmin):
    _request_stash = None

    change_list_template = (
        "admin/industry/industrylpstoreoffer/change_list.html"
    )
    # Fuzzwork-like order: identity, offer costs, requirements, market, rates.
    list_display = (
        "type_name_display",
        "currency_display",
        "lp_cost_display",
        "isk_cost_display",
        "quantity",
        "required_items_display",
        "other_cost_display",
        "jita_sell_display",
        "jita_buy_display",
        "conversion_sell_display",
        "conversion_buy_display",
        "volume_1d_display",
        "volume_7d_display",
        "volume_30d_display",
        "updated_at",
    )
    list_filter = (
        IndustryLpStoreCurrencyListFilter,
        IndustryLpStoreExcludeTagsFilter,
        IndustryLpStoreExcludeSupplyPackagesFilter,
        IndustryLpStoreExcludeChipsFilter,
        IndustryLpStoreExcludeUselessOffersFilter,
        IndustryLpStoreExcludeBelowSetLpPriceFilter,
    )
    search_fields = ("offer_id", "type_id", "corporation_id")
    ordering = ("corporation_id", "type_id")
    actions = ("sync_loyalty_store_offers_action",)
    readonly_fields = (
        "offer_id",
        "corporation_id",
        "type_id",
        "lp_cost",
        "isk_cost",
        "ak_cost",
        "quantity",
        "updated_at",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "offer_id",
                    "corporation_id",
                    "type_id",
                    "lp_cost",
                    "isk_cost",
                    "ak_cost",
                    "quantity",
                    "updated_at",
                ),
                "description": (
                    "Read-only ESI cache for tracked LP currencies. "
                    "Refresh via Celery beat, navy product sync, planner "
                    "miss, or sync action."
                ),
            },
        ),
    )

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .filter(corporation_id__in=tracked_corporation_ids())
        )
        return annotate_lp_store_offer_sort_fields(qs)

    def get_search_results(self, request, queryset, search_term):
        # queryset already has list filters applied (e.g. currency). Keep a
        # copy so name search cannot reintroduce rows those filters excluded.
        filtered_qs = queryset
        queryset, use_distinct = super().get_search_results(
            request, queryset, search_term
        )
        term = (search_term or "").strip()
        if not term:
            return queryset, use_distinct
        type_ids = list(
            EveType.objects.filter(name__icontains=term).values_list(
                "id", flat=True
            )
        )
        if type_ids:
            by_name = filtered_qs.filter(type_id__in=type_ids)
            queryset |= by_name
            use_distinct = True
        return queryset, use_distinct

    def get_changelist_instance(self, request):
        # Warm full-catalog economics before ChangeList applies filters so
        # exclude-useless / exclude-below-set share one compute with stash.
        if _lp_econ_filters_active(request):
            ensure_lp_offer_econ_on_request(request)
        cl = super().get_changelist_instance(request)
        cached = getattr(request, _LP_OFFER_ECON_ATTR, None)
        if cached is not None:
            IndustryLpStoreOfferAdmin._request_stash = cached
        else:
            IndustryLpStoreOfferAdmin._request_stash = (
                offer_economics_for_queryset(list(cl.result_list))
            )
        return cl

    def changelist_view(self, request, extra_context=None):
        # TemplateResponse renders after this method returns; force render
        # while economics stash is still populated so list_display methods
        # can resolve type names and market columns.
        try:
            response = super().changelist_view(
                request, extra_context=extra_context
            )
            if hasattr(response, "render"):
                response.render()
            return response
        finally:
            IndustryLpStoreOfferAdmin._request_stash = None
            if hasattr(request, _LP_OFFER_ECON_ATTR):
                delattr(request, _LP_OFFER_ECON_ATTR)

    @classmethod
    def _econ_for(cls, obj):
        stash = cls._request_stash
        if not stash:
            return None
        return stash.get(obj.pk)

    @classmethod
    def _format_isk(cls, obj, attr: str) -> str:
        econ = cls._econ_for(obj)
        if econ is None:
            return "—"
        value = getattr(econ, attr)
        if value is None:
            return "—"
        return f"{value:,}"

    @classmethod
    def _format_rate(cls, obj, attr: str) -> str:
        econ = cls._econ_for(obj)
        if econ is None:
            return "—"
        value = getattr(econ, attr)
        if value is None:
            return "—"
        return f"{value:,.1f}"

    @admin.display(description="Item", ordering="sort_type_name")
    def type_name_display(self, obj):
        econ = self._econ_for(obj)
        type_id = obj.type_id
        is_blueprint = False
        if econ is None:
            name = (
                EveType.objects.filter(id=type_id)
                .values_list("name", flat=True)
                .first()
            )
            resolved = bool(name)
            name = name or str(type_id)
            # Heuristic when stash is cold; prefer economics.kind when live.
            is_blueprint = "blueprint" in str(name).lower()
        elif econ.kind == "blueprint" and econ.market_type_id != econ.type_id:
            name = f"{econ.market_type_name} (BPC)"
            type_id = econ.type_id
            is_blueprint = True
            resolved = bool(econ.market_type_name) and (
                econ.market_type_name != str(econ.market_type_id)
            )
        else:
            name = econ.type_name
            type_id = econ.type_id
            is_blueprint = econ.kind == "blueprint"
            resolved = bool(econ.type_name) and econ.type_name != str(type_id)

        title = f"Type {type_id}"
        image_path = "bp" if is_blueprint else "icon"
        if resolved:
            return format_html(
                '<span class="lp-store-offer-item" title="{}">'
                '<img class="lp-store-offer-item__icon" '
                'src="https://images.evetech.net/types/{}/{}?size=32" '
                'width="32" height="32" alt="" loading="lazy" '
                'onerror="this.hidden=true;'
                'this.nextElementSibling.hidden=false;" />'
                '<span class="lp-store-offer-item__placeholder" '
                'aria-hidden="true" hidden></span>'
                '<span class="lp-store-offer-item__name">{}</span>'
                "</span>",
                title,
                type_id,
                image_path,
                name,
            )
        return format_html(
            '<span class="lp-store-offer-item '
            'lp-store-offer-item--missing" title="{}">'
            '<span class="lp-store-offer-item__placeholder" '
            'aria-hidden="true"></span>'
            '<span class="lp-store-offer-item__name">{}</span>'
            "</span>",
            title,
            name,
        )

    @admin.display(description="LP cost", ordering="lp_cost")
    def lp_cost_display(self, obj):
        return f"{obj.lp_cost:,}"

    @admin.display(description="ISK cost", ordering="isk_cost")
    def isk_cost_display(self, obj):
        return f"{obj.isk_cost:,}"

    @admin.display(description="Currency")
    def currency_display(self, obj):
        econ = self._econ_for(obj)
        if econ is not None:
            return econ.currency_name
        currency = (
            IndustryLoyaltyPoint.objects.filter(
                corporation_id=obj.corporation_id
            )
            .values_list("name", flat=True)
            .first()
        )
        return currency or str(obj.corporation_id)

    @admin.display(description="Required")
    def required_items_display(self, obj):
        econ = self._econ_for(obj)
        if econ is None or not econ.required_items_summary:
            return "—"
        return econ.required_items_summary

    @admin.display(description="Other cost")
    def other_cost_display(self, obj):
        return self._format_isk(obj, "other_cost")

    @admin.display(description="Buyback ISK/LP")
    def isk_per_lp_display(self, obj):
        econ = self._econ_for(obj)
        if econ is None or econ.isk_per_lp is None:
            return "—"
        return f"{econ.isk_per_lp:,.0f}"

    @admin.display(description="ISK/LP sell", ordering="sort_conversion_sell")
    def conversion_sell_display(self, obj):
        return self._format_rate(obj, "conversion_isk_per_lp_sell")

    @admin.display(description="ISK/LP buy", ordering="sort_conversion_buy")
    def conversion_buy_display(self, obj):
        return self._format_rate(obj, "conversion_isk_per_lp_buy")

    @admin.display(description="Jita sell", ordering="sort_jita_price")
    def jita_sell_display(self, obj):
        return self._format_isk(obj, "jita_sell")

    @admin.display(description="Jita buy", ordering="sort_jita_price")
    def jita_buy_display(self, obj):
        return self._format_isk(obj, "jita_buy")

    @admin.display(description="1d vol", ordering="sort_volume_1d")
    def volume_1d_display(self, obj):
        return self._format_isk(obj, "volume_1d")

    @admin.display(description="7d vol", ordering="sort_volume_7d")
    def volume_7d_display(self, obj):
        return self._format_isk(obj, "volume_7d")

    @admin.display(description="30d vol", ordering="sort_volume_30d")
    def volume_30d_display(self, obj):
        return self._format_isk(obj, "volume_30d")

    @admin.display(description="Acquisition", ordering="sort_acquisition")
    def cost_display(self, obj):
        return self._format_isk(obj, "cost_per_unit")

    @admin.display(description="Profit vs sell", ordering="sort_profit")
    def profit_vs_sell_display(self, obj):
        return self._format_isk(obj, "profit_vs_sell")

    @admin.action(description="Sync LP store offers from ESI now")
    def sync_loyalty_store_offers_action(self, request, queryset):
        del queryset  # whole-cache sync; selection unused
        try:
            count = sync_loyalty_store_offers_task()
        except Exception as exc:  # noqa: BLE001 — surface ESI failures
            self.message_user(
                request,
                f"LP store sync failed: {exc}",
                level=messages.ERROR,
            )
            return
        self.message_user(
            request,
            f"Synced {count} loyalty-store offer(s).",
            level=messages.SUCCESS,
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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

    def save_related(self, request, form, formsets, change):
        """Enqueue profit snapshot after order items exist on the order."""
        super().save_related(request, form, formsets, change)
        order = form.instance
        if not order.pk:
            return
        try:
            compute_order_profit_breakdown_task.delay(order.pk)
        except Exception:  # noqa: BLE001 — never fail admin save on planner
            logger.exception(
                "Failed to enqueue profit breakdown for order %s", order.pk
            )

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
        "delivered_quantity",
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
        "delivered_quantity",
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

INDUSTRY_LOYALTY_HIDDEN_MODELS = {
    "industryloyaltypoint",
    "industryloyaltypointaccount",
    "industryloyaltypointcontact",
    "industryloyaltypointledgerentry",
    "industryloyaltypointmarketorder",
    "industrylpstoreoffer",
}

INDUSTRY_SUPPLY_EXCLUDED_MODELS = (
    INDUSTRY_ORDERS_HIDDEN_MODELS
    | INDUSTRY_LOYALTY_HIDDEN_MODELS
    | {
        "industryproduct",
        "miningupgradecompletion",
    }
)

INDUSTRY_EXPERIMENTAL_VISIBLE_RENAMES = {
    "industryproduct": "Products",
    "miningupgradecompletion": "Mining completions",
}

INDUSTRY_SUPPLY_EXTRA_INDEX_LINKS = [
    {
        "name": "Industry orders",
        "admin_url": "admin:industry_orders_home",
        "perms": industry_orders_index_link_perms,
    },
    {
        "name": "Loyalty points",
        "admin_url": "admin:industry_loyalty_home",
        "perms": loyalty_index_link_perms,
    },
]

# Back-compat alias used by older tests / imports.
INDUSTRY_ORDERS_EXTRA_INDEX_LINKS = INDUSTRY_SUPPLY_EXTRA_INDEX_LINKS[:1]

_INDUSTRY_ADMIN_PATCHED_ATTR = "industry_admin_patched"


def _build_industry_supply_index_links(request) -> list[dict]:
    links = []
    for extra in INDUSTRY_SUPPLY_EXTRA_INDEX_LINKS:
        links.append(
            {
                "name": extra["name"],
                "object_name": extra["name"],
                "perms": extra["perms"](request.user),
                "admin_url": reverse(extra["admin_url"]),
                "view_only": extra.get("view_only", False),
            }
        )
    return links


def _build_industry_orders_index_link(request) -> dict:
    """Back-compat helper for tests that expect a single orders link."""
    return _build_industry_supply_index_links(request)[0]


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
            for index, link in enumerate(
                _build_industry_supply_index_links(request)
            ):
                models.insert(index, link)
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
        path(
            "industry/loyalty/",
            admin.site.admin_view(industry_loyalty_home_view),
            name="industry_loyalty_home",
        ),
    ]


def apply_industry_admin_customizations():
    """Chain industry hub URLs and Supply sidebar entries."""
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
