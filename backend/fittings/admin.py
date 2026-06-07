import json

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Count, Exists, OuterRef, Subquery
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from safedelete.admin import SafeDeleteAdmin, SafeDeleteAdminFilter

from eveuniverse.models import EveType

from fittings.helpers.doctrine_changes import (
    apply_doctrine_payload,
    approve_doctrine_change_request,
    build_doctrine_payload_from_form,
    cancel_doctrine_change_request,
    reject_doctrine_change_request,
    submit_doctrine_change_request,
)
from fittings.helpers.fitting_changes import (
    approve_fitting_change_request,
    build_fitting_payload_from_instance,
    build_refit_payload,
    cancel_fitting_change_request,
    reject_fitting_change_request,
    submit_fitting_change_request,
)
from fittings.helpers.permissions import (
    can_approve_doctrine_request,
    can_approve_fitting_request,
    can_publish_doctrine_change,
    can_publish_fitting_change,
    effective_protection_tier,
    protection_tier_for_doctrine,
)
from fittings.models import (
    ChangeRequestStatus,
    EveDoctrine,
    EveDoctrineChangeRequest,
    EveDoctrineFitting,
    EveDoctrineHistory,
    EveFitting,
    EveFittingChangeRequest,
    EveFittingHistory,
    EveFittingPod,
    EveFittingRefit,
    FittingTag,
)
from fittings.tasks import (
    notify_doctrine_change_request_proposed,
    notify_fitting_change_request_proposed,
)
from srp.models import PodReimbursementProgram

from .forms import EveDoctrineForm, EveFittingAdminForm


def _mark_change_request_queued(request, redirect_url: str) -> None:
    # pylint: disable=protected-access
    request._change_request_queued = True
    request._change_request_redirect_url = redirect_url


def _warn_if_refit_edited_after_fitting_queued(request, formset) -> None:
    refit_edited = any(
        inline_form.has_changed()
        for inline_form in formset.forms
        if inline_form.cleaned_data
        and not inline_form.cleaned_data.get("DELETE")
    )
    if refit_edited:
        messages.warning(
            request,
            "Fitting change was queued; inline refit edits were not "
            "included. Save refit changes in a separate submit after "
            "approval.",
        )


def _queue_refit_delete_request(
    request, fitting, inline_form, user
) -> tuple[bool, bool]:
    """Return (queued, abort). abort True if user should stop processing."""
    try:
        req = submit_fitting_change_request(
            fitting,
            change_kind="refit_delete",
            payload=build_refit_payload(inline_form.instance),
            user=user,
            refit=inline_form.instance,
        )
        if req:
            notify_fitting_change_request_proposed.delay(req.pk)
            return True, False
    except (PermissionError, ValueError) as exc:
        messages.error(request, str(exc))
        return False, True
    return False, False


def _queue_refit_upsert_request(
    request, fitting, inline_form, user
) -> tuple[bool, bool]:
    """Return (queued, abort). abort True if user should stop processing."""
    refit = inline_form.instance
    payload = {
        "name": inline_form.cleaned_data.get("name", refit.name),
        "eft_format": inline_form.cleaned_data.get(
            "eft_format", refit.eft_format
        ),
        "description": inline_form.cleaned_data.get(
            "description", refit.description or ""
        ),
    }
    kind = "refit_update" if refit.pk else "refit_create"
    try:
        req = submit_fitting_change_request(
            fitting,
            change_kind=kind,
            payload=payload,
            user=user,
            refit=refit if refit.pk else None,
        )
        if req:
            notify_fitting_change_request_proposed.delay(req.pk)
            return True, False
    except (PermissionError, ValueError) as exc:
        messages.error(request, str(exc))
        return False, True
    return False, False


class ApprovalQueuedAdminMixin:  # pylint: disable=protected-access
    """Avoid false 'saved successfully' when a change is queued for approval."""

    def log_addition(self, request, obj, message):
        if getattr(request, "_change_request_queued", False):
            return
        return super().log_addition(request, obj, message)

    def log_change(self, request, obj, message):
        if getattr(request, "_change_request_queued", False):
            return
        return super().log_change(request, obj, message)

    def response_add(self, request, obj):
        if getattr(request, "_change_request_queued", False):
            return HttpResponseRedirect(request._change_request_redirect_url)
        return super().response_add(request, obj)

    def response_change(self, request, obj):
        if getattr(request, "_change_request_queued", False):
            return HttpResponseRedirect(request._change_request_redirect_url)
        return super().response_change(request, obj)


class FittingTagListFilter(admin.SimpleListFilter):
    title = "tag"
    parameter_name = "fitting_tag"

    def lookups(self, request, model_admin):
        return FittingTag.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(tags__contains=[self.value()])
        return queryset


class HasFittingPodsListFilter(admin.SimpleListFilter):
    title = "fitting pods"
    parameter_name = "has_fitting_pods"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
            ("legacy", "Legacy text only"),
        )

    def queryset(self, request, queryset):
        has_pods = EveFittingPod.objects.filter(fittings=OuterRef("pk"))
        has_legacy = models.Q(minimum_pod__gt="") | models.Q(
            recommended_pod__gt=""
        )
        if self.value() == "yes":
            return queryset.filter(Exists(has_pods))
        if self.value() == "no":
            return queryset.filter(~Exists(has_pods)).exclude(has_legacy)
        if self.value() == "legacy":
            return queryset.filter(~Exists(has_pods)).filter(has_legacy)
        return queryset


class HasRefitsListFilter(admin.SimpleListFilter):
    title = "has refits"
    parameter_name = "has_refits"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(
                Exists(
                    EveFittingRefit.objects.filter(
                        base_fitting_id=OuterRef("pk")
                    )
                )
            )
        if self.value() == "no":
            return queryset.filter(
                ~Exists(
                    EveFittingRefit.objects.filter(
                        base_fitting_id=OuterRef("pk")
                    )
                )
            )
        return queryset


class InDoctrineListFilter(admin.SimpleListFilter):
    title = "doctrine"
    parameter_name = "in_doctrine"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Doctrine"),
            ("no", "No Doctrine"),
        )

    def queryset(self, request, queryset):
        in_any_doctrine = EveDoctrineFitting.objects.filter(
            fitting_id=OuterRef("pk")
        )
        if self.value() == "yes":
            return queryset.filter(Exists(in_any_doctrine))
        if self.value() == "no":
            return queryset.filter(~Exists(in_any_doctrine))
        return queryset


class EveFittingRefitInline(admin.StackedInline):
    model = EveFittingRefit
    extra = 0
    show_change_link = True
    fields = (
        "name",
        "eft_format",
        "description",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(EveFitting)
class EveFittingAdmin(ApprovalQueuedAdminMixin, SafeDeleteAdmin):
    """Admin screen for EveFitting entity. Ship is inferred from EFT; display name is editable."""

    form = EveFittingAdminForm
    field_to_highlight = "name"

    filter_horizontal = ("pods",)
    list_display = (
        "highlight_deleted_field",
        "ship_name",
        "pod_count",
        "refit_count",
        "description",
        "deleted",
    )
    search_fields = ("name", "description", "aliases")
    list_filter = (
        SafeDeleteAdminFilter,
        HasFittingPodsListFilter,
        HasRefitsListFilter,
        InDoctrineListFilter,
        FittingTagListFilter,
    )
    list_per_page = 50
    ordering = ("name",)
    readonly_fields = (
        "ship_id",
        "latest_version",
        "created_at",
        "updated_at",
        "protection_tier_display",
    )
    fieldsets = (
        (
            "Fitting",
            {
                "fields": (
                    "name",
                    "ship_id",
                    "latest_version",
                    "protection_tier_display",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
        (
            "EFT & description",
            {
                "fields": ("eft_format", "description", "tags"),
            },
        ),
        (
            "Aliases",
            {
                "description": (
                    "Used when resolving contracts and search; not shown on the public "
                    "fitting name."
                ),
                "fields": ("aliases",),
            },
        ),
        (
            "Pods",
            {
                "description": (
                    "Link EveFittingPod loadouts here. Legacy text fields remain "
                    "for reference during migration."
                ),
                "fields": ("pods", "minimum_pod", "recommended_pod"),
            },
        ),
    )
    inlines = (EveFittingRefitInline,)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        ship_sq = EveType.objects.filter(pk=OuterRef("ship_id")).values(
            "name"
        )[:1]
        return qs.annotate(
            _pod_count=Count("pods", distinct=True),
            _refit_count=Count("refits"),
            _ship_name=Subquery(ship_sq),
        )

    @admin.display(description="Ship", ordering="_ship_name")
    def ship_name(self, obj):
        return getattr(obj, "_ship_name", None) or "—"

    @admin.display(description="Refits", ordering="_refit_count")
    def refit_count(self, obj):
        return getattr(obj, "_refit_count", 0)

    @admin.display(description="Pods", ordering="_pod_count")
    def pod_count(self, obj):
        return getattr(obj, "_pod_count", 0)

    @admin.display(description="Protection tier")
    def protection_tier_display(self, obj):
        if not obj.pk:
            return "—"
        tier = effective_protection_tier(obj)
        return tier or "none (immediate publish)"

    def _prepare_fitting_from_form(self, obj, form):
        eft_format = form.cleaned_data.get("eft_format") or getattr(
            obj, "eft_format", ""
        )
        if eft_format and eft_format.strip():
            derived_name = EveFitting.fitting_name_from_eft(eft_format)
            if not (obj.name and str(obj.name).strip()) and derived_name:
                obj.name = derived_name
            ship_name = EveFitting.ship_name_from_eft(eft_format)
            if ship_name:
                eve_type = EveType.objects.filter(name=ship_name).first()
                if eve_type is not None:
                    obj.ship_id = eve_type.id

    def save_model(self, request, obj, form, change):
        self._prepare_fitting_from_form(obj, form)

        if not change:
            obj.description = obj.description or ""
            super().save_model(request, obj, form, change)
            return

        tier = effective_protection_tier(obj)
        payload = build_fitting_payload_from_instance(obj)
        for field in payload:
            if field in form.cleaned_data:
                payload[field] = form.cleaned_data[field]

        if tier is None or can_publish_fitting_change(request.user, tier):
            for field, value in payload.items():
                setattr(obj, field, value)
            super().save_model(request, obj, form, change)
            return

        try:
            req = submit_fitting_change_request(
                obj,
                change_kind="fitting_versioned",
                payload=payload,
                user=request.user,
            )
        except (PermissionError, ValueError) as exc:
            messages.error(request, str(exc))
            return

        if req:
            notify_fitting_change_request_proposed.delay(req.pk)
            url = reverse(
                "admin:fittings_evefittingchangerequest_change",
                args=[req.pk],
            )
            messages.warning(
                request,
                format_html(
                    "Fitting change submitted for approval. "
                    '<a href="{}">View request</a>.',
                    url,
                ),
            )
            _mark_change_request_queued(request, url)

    def save_formset(self, request, form, formset, change):
        if formset.model is not EveFittingRefit:
            return super().save_formset(request, form, formset, change)

        if getattr(request, "_change_request_queued", False):
            _warn_if_refit_edited_after_fitting_queued(request, formset)
            return

        fitting = form.instance
        if not fitting.pk:
            super().save_formset(request, form, formset, change)
            return

        tier = effective_protection_tier(fitting)
        if tier is None or can_publish_fitting_change(request.user, tier):
            return super().save_formset(request, form, formset, change)

        queued = False
        for inline_form in formset.forms:
            is_delete = (
                not inline_form.cleaned_data
                or inline_form.cleaned_data.get("DELETE")
            )
            if is_delete:
                if inline_form.instance.pk:
                    q, abort = _queue_refit_delete_request(
                        request, fitting, inline_form, request.user
                    )
                    if abort:
                        return
                    queued = queued or q
                continue

            q, abort = _queue_refit_upsert_request(
                request, fitting, inline_form, request.user
            )
            if abort:
                return
            queued = queued or q

        if queued:
            messages.warning(
                request,
                "Refit change(s) submitted for approval (live refits unchanged).",
            )


EveFittingAdmin.highlight_deleted_field.short_description = "Name"


@admin.register(EveFittingHistory)
class EveFittingHistoryAdmin(admin.ModelAdmin):
    """Read-only audit of previous fitting versions."""

    list_display = (
        "fitting",
        "superseded_version_id",
        "name",
        "created_at",
    )
    list_filter = ("fitting",)
    search_fields = ("name", "superseded_version_id", "fitting__name")
    raw_id_fields = ("fitting",)
    ordering = ("-created_at",)
    readonly_fields = (
        "id",
        "fitting",
        "superseded_version_id",
        "name",
        "ship_id",
        "eft_format",
        "description",
        "aliases",
        "minimum_pod",
        "recommended_pod",
        "tags",
        "created_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(EveFittingRefit)
class EveFittingRefitAdmin(admin.ModelAdmin):
    """Admin screen for EveFittingRefit entity"""

    list_display = ("name", "base_fitting_link", "updated_at")
    list_filter = ("base_fitting",)
    search_fields = ("name", "description", "base_fitting__name")
    autocomplete_fields = ("base_fitting",)
    ordering = ("base_fitting", "name")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Base", {"fields": ("base_fitting",)}),
        ("Refit", {"fields": ("name", "eft_format", "description")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Base fitting", ordering="base_fitting")
    def base_fitting_link(self, obj):
        if obj.base_fitting_id:
            url = reverse(
                "admin:fittings_evefitting_change", args=[obj.base_fitting_id]
            )
            return format_html('<a href="{}">{}</a>', url, obj.base_fitting)
        return "—"

    def save_model(self, request, obj, form, change):
        tier = effective_protection_tier(obj.base_fitting)
        payload = build_refit_payload(obj)
        for key in payload:
            if key in form.cleaned_data:
                payload[key] = form.cleaned_data[key]

        if not change:
            if tier is None or can_publish_fitting_change(request.user, tier):
                super().save_model(request, obj, form, change)
                return
            if not obj.base_fitting_id:
                messages.error(request, "Base fitting is required.")
                return
            try:
                req = submit_fitting_change_request(
                    obj.base_fitting,
                    change_kind="refit_create",
                    payload=payload,
                    user=request.user,
                )
            except (PermissionError, ValueError) as exc:
                messages.error(request, str(exc))
                return
            if req:
                notify_fitting_change_request_proposed.delay(req.pk)
                messages.warning(
                    request, "Refit creation submitted for approval."
                )
            return

        if tier is None or can_publish_fitting_change(request.user, tier):
            super().save_model(request, obj, form, change)
            return

        try:
            req = submit_fitting_change_request(
                obj.base_fitting,
                change_kind="refit_update",
                payload=payload,
                user=request.user,
                refit=obj,
            )
        except (PermissionError, ValueError) as exc:
            messages.error(request, str(exc))
            return
        if req:
            notify_fitting_change_request_proposed.delay(req.pk)
            messages.warning(request, "Refit change submitted for approval.")


class ChangeRequestAdminMixin:
    """Approve / reject / cancel actions for change request admins."""

    def changelist_view(self, request, extra_context=None):
        if "status" not in request.GET and "status__exact" not in request.GET:
            q = request.GET.copy()
            q["status__exact"] = ChangeRequestStatus.PENDING
            return HttpResponseRedirect(f"{request.path}?{q.urlencode()}")
        return super().changelist_view(request, extra_context)

    @admin.display(description="Payload")
    def payload_display(self, obj):
        if obj is None:
            return "—"
        text = json.dumps(obj.payload, indent=2, sort_keys=True, default=str)
        return format_html('<pre style="white-space:pre-wrap">{}</pre>', text)

    def _check_approve(self, request, change_request):
        tier = change_request.tier
        if isinstance(change_request, EveDoctrineChangeRequest):
            if not can_approve_doctrine_request(request.user, tier):
                raise PermissionDenied(
                    "You cannot approve this doctrine change request."
                )
        elif not can_approve_fitting_request(request.user, tier):
            raise PermissionDenied(
                "You cannot approve this fitting change request."
            )

    @admin.action(description="Approve selected pending requests")
    def approve_requests(self, request, queryset):
        pending = queryset.filter(status=ChangeRequestStatus.PENDING)
        count = 0
        for change_request in pending:
            try:
                self._check_approve(request, change_request)
                if isinstance(change_request, EveDoctrineChangeRequest):
                    approve_doctrine_change_request(
                        change_request, request.user
                    )
                else:
                    approve_fitting_change_request(
                        change_request, request.user
                    )
                count += 1
            except (PermissionDenied, ValueError) as exc:
                messages.error(request, str(exc))
                return
        messages.success(request, f"Approved {count} request(s).")

    @admin.action(description="Reject selected pending requests")
    def reject_requests(self, request, queryset):
        pending = queryset.filter(status=ChangeRequestStatus.PENDING)
        count = 0
        for change_request in pending:
            try:
                self._check_approve(request, change_request)
                if isinstance(change_request, EveDoctrineChangeRequest):
                    reject_doctrine_change_request(
                        change_request, request.user
                    )
                else:
                    reject_fitting_change_request(change_request, request.user)
                count += 1
            except (PermissionDenied, ValueError) as exc:
                messages.error(request, str(exc))
                return
        messages.success(request, f"Rejected {count} request(s).")

    @admin.action(
        description="Cancel selected pending requests (submitter or superuser)"
    )
    def cancel_requests(self, request, queryset):
        pending = queryset.filter(status=ChangeRequestStatus.PENDING)
        count = 0
        for change_request in pending:
            if not (
                request.user.is_superuser
                or change_request.submitted_by_id == request.user.id
            ):
                messages.error(
                    request,
                    "You can only cancel your own pending requests.",
                )
                return
            try:
                if isinstance(change_request, EveDoctrineChangeRequest):
                    cancel_doctrine_change_request(
                        change_request, request.user
                    )
                else:
                    cancel_fitting_change_request(change_request, request.user)
                count += 1
            except ValueError as exc:
                messages.error(request, str(exc))
                return
        messages.success(request, f"Cancelled {count} request(s).")


@admin.register(EveDoctrineChangeRequest)
class EveDoctrineChangeRequestAdmin(ChangeRequestAdminMixin, admin.ModelAdmin):
    list_display = (
        "doctrine",
        "tier",
        "status",
        "submitted_by",
        "submitted_at",
        "reviewed_by",
    )
    list_filter = ("status", "tier")
    search_fields = ("doctrine__name", "submitted_by__username")
    readonly_fields = (
        "doctrine",
        "tier",
        "change_kind",
        "payload_display",
        "submitted_by",
        "submitted_at",
        "reviewed_by",
        "reviewed_at",
        "review_note",
    )
    actions = ["approve_requests", "reject_requests", "cancel_requests"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(EveFittingChangeRequest)
class EveFittingChangeRequestAdmin(ChangeRequestAdminMixin, admin.ModelAdmin):
    list_display = (
        "fitting",
        "change_kind",
        "tier",
        "status",
        "submitted_by",
        "submitted_at",
    )
    list_filter = ("status", "tier", "change_kind")
    search_fields = ("fitting__name", "submitted_by__username")
    readonly_fields = (
        "fitting",
        "refit",
        "tier",
        "change_kind",
        "payload_display",
        "submitted_by",
        "submitted_at",
        "reviewed_by",
        "reviewed_at",
        "review_note",
    )
    actions = ["approve_requests", "reject_requests", "cancel_requests"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff


@admin.register(EveDoctrineHistory)
class EveDoctrineHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "doctrine",
        "superseded_version_id",
        "name",
        "type",
        "created_at",
    )
    list_filter = ("doctrine", "type")
    search_fields = ("name", "doctrine__name")
    raw_id_fields = ("doctrine",)
    ordering = ("-created_at",)
    readonly_fields = (
        "doctrine",
        "superseded_version_id",
        "name",
        "type",
        "description",
        "composition",
        "location_ids",
        "created_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(EveDoctrine)
class EveDoctrineAdmin(ApprovalQueuedAdminMixin, admin.ModelAdmin):
    """
    Custom admin to make editing doctrines easier
    """

    form = EveDoctrineForm
    list_display = ("name", "type", "description")
    search_fields = ("name", "type", "description")
    ordering = ("name",)

    def save_model(self, request, obj, form, change):
        payload = build_doctrine_payload_from_form(form.cleaned_data)

        if not change:
            tier = protection_tier_for_doctrine(obj)
            if tier is None:
                if not obj.pk:
                    obj.save()
                apply_doctrine_payload(obj, payload)
                return
            if can_publish_doctrine_change(request.user, tier):
                if not obj.pk:
                    obj.save()
                apply_doctrine_payload(obj, payload)
                return
            try:
                req = submit_doctrine_change_request(
                    obj,
                    payload,
                    request.user,
                    ensure_doctrine_row=True,
                )
            except (PermissionError, ValueError) as exc:
                messages.error(request, str(exc))
                return
            if req:
                notify_doctrine_change_request_proposed.delay(req.pk)
                url = reverse(
                    "admin:fittings_evedoctrinechangerequest_change",
                    args=[req.pk],
                )
                messages.warning(
                    request,
                    format_html(
                        "Doctrine submitted for approval. "
                        '<a href="{}">View request</a>.',
                        url,
                    ),
                )
                _mark_change_request_queued(request, url)
            return

        tier = protection_tier_for_doctrine(obj)
        if tier is None or can_publish_doctrine_change(request.user, tier):
            apply_doctrine_payload(obj, payload)
            return

        try:
            req = submit_doctrine_change_request(obj, payload, request.user)
        except (PermissionError, ValueError) as exc:
            messages.error(request, str(exc))
            return
        if req:
            notify_doctrine_change_request_proposed.delay(req.pk)
            url = reverse(
                "admin:fittings_evedoctrinechangerequest_change",
                args=[req.pk],
            )
            messages.warning(
                request,
                format_html(
                    "Doctrine change submitted for approval. "
                    '<a href="{}">View request</a>.',
                    url,
                ),
            )
            _mark_change_request_queued(request, url)


class HasFittingsPodFilter(admin.SimpleListFilter):
    title = "has fittings"
    parameter_name = "has_fittings"

    def lookups(self, request, model_admin):
        return (("yes", "Yes"), ("no", "No"))

    def queryset(self, request, queryset):
        has_fittings = EveFitting.objects.filter(pods=OuterRef("pk"))
        if self.value() == "yes":
            return queryset.filter(Exists(has_fittings))
        if self.value() == "no":
            return queryset.filter(~Exists(has_fittings))
        return queryset


class HasEscapeFrigatesPodFilter(admin.SimpleListFilter):
    title = "has escape frigates"
    parameter_name = "has_escape_frigates"

    def lookups(self, request, model_admin):
        return (("yes", "Yes"), ("no", "No"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(
                escape_frigate_fittings__isnull=False
            ).distinct()
        if self.value() == "no":
            return queryset.filter(escape_frigate_fittings__isnull=True)
        return queryset


@admin.register(EveFittingPod)
class EveFittingPodAdmin(SafeDeleteAdmin):
    list_display = (
        "highlight_deleted_field",
        "name",
        "priority",
        "fitting_count",
        "escape_frigate_count",
        "current_srp_value",
        "deleted",
    )
    search_fields = ("name", "description", "pod_format")
    list_filter = (
        SafeDeleteAdminFilter,
        HasFittingsPodFilter,
        HasEscapeFrigatesPodFilter,
    )
    filter_horizontal = ("escape_frigate_fittings",)
    readonly_fields = ("linked_fittings", "current_srp_value")
    fields = (
        "name",
        "priority",
        "description",
        "pod_format",
        "escape_frigate_fittings",
        "linked_fittings",
        "current_srp_value",
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _fitting_count=Count("fittings", distinct=True),
            _escape_frigate_count=Count(
                "escape_frigate_fittings", distinct=True
            ),
        )

    @admin.display(description="Fittings", ordering="_fitting_count")
    def fitting_count(self, obj):
        return getattr(obj, "_fitting_count", 0)

    @admin.display(
        description="Escape frigates", ordering="_escape_frigate_count"
    )
    def escape_frigate_count(self, obj):
        return getattr(obj, "_escape_frigate_count", 0)

    @admin.display(description="Linked fittings")
    def linked_fittings(self, obj):
        if not obj.pk:
            return "Save pod first."
        names = obj.fittings.order_by("name").values_list("name", flat=True)
        if not names:
            return "None"
        return format_html("<br>".join(names))

    @admin.display(description="Current SRP value")
    def current_srp_value(self, obj):
        if not obj.pk:
            return None
        program = (
            PodReimbursementProgram.objects.filter(fitting_pod=obj)
            .order_by("-id")
            .first()
        )
        if not program:
            return None
        latest = program.amounts.order_by("-created_at", "-id").first()
        return latest.srp_value if latest else None

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "escape_frigate_fittings":
            kwargs["queryset"] = EveFitting.objects.filter(
                tags__contains=[FittingTag.ESCAPE_FRIGATE]
            )
        return super().formfield_for_manytomany(db_field, request, **kwargs)
