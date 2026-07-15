from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.db.models import Count, Exists, OuterRef, Subquery
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from safedelete.admin import SafeDeleteAdmin, SafeDeleteAdminFilter

from eveuniverse.models import EveType

from fittings.admin_list_views import (
    doctrines_manage_view,
    fittings_manage_view,
)
from fittings.helpers.admin_permissions import (
    index_link_perms,
    user_can_view_doctrines_admin,
    user_can_view_fittings_admin,
)
from fittings.helpers.change_request_display import (
    DOCTRINE_TYPE_LABELS,
    format_doctrine_change_request_html,
    format_doctrine_history_html,
    format_fitting_change_request_html,
    format_fitting_history_html,
)
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
    build_fitting_payload_from_form,
    build_fitting_payload_from_instance,
    build_refit_payload,
    cancel_fitting_change_request,
    fitting_change_request_tier,
    fitting_payload_changed,
    reject_fitting_change_request,
    submit_fitting_change_request,
)
from fittings.helpers.permissions import (
    can_approve_doctrine_request,
    can_approve_fitting_request,
    can_propose_doctrine_change,
    can_propose_fitting_change,
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

from .forms import (
    ChangeRequestReviewForm,
    EveDoctrineChangeRequestAdminForm,
    EveDoctrineForm,
    EveFittingAdminForm,
    EveFittingChangeRequestAdminForm,
    EveFittingRefitInlineForm,
)

_SELF_APPROVAL_WARNING = (
    "You submitted this request. Approving your own changes bypasses "
    "independent review."
)


def _mark_change_request_queued(request, redirect_url: str) -> None:
    # pylint: disable=protected-access
    request._change_request_queued = True
    request._change_request_redirect_url = redirect_url


def _mark_refit_formset_handled(formset) -> None:
    """formset.save() normally sets these for construct_change_message()."""
    formset.new_objects = []
    formset.changed_objects = []
    formset.deleted_objects = []


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
    eft_format = inline_form.cleaned_data.get("eft_format", refit.eft_format)
    derived_name = EveFitting.fitting_name_from_eft(eft_format)
    payload = {
        "name": derived_name
        or inline_form.cleaned_data.get("name", refit.name),
        "eft_format": eft_format,
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

    def log_deletion(self, request, obj, object_repr):
        if getattr(request, "_change_request_queued", False):
            return
        return super().log_deletion(request, obj, object_repr)

    def response_add(self, request, obj):
        if getattr(request, "_change_request_queued", False):
            return HttpResponseRedirect(request._change_request_redirect_url)
        return super().response_add(request, obj)

    def response_change(self, request, obj):
        if getattr(request, "_change_request_queued", False):
            return HttpResponseRedirect(request._change_request_redirect_url)
        return super().response_change(request, obj)

    def response_delete(self, request, obj_display, obj_id):
        if getattr(request, "_change_request_queued", False):
            return HttpResponseRedirect(request._change_request_redirect_url)
        return super().response_delete(request, obj_display, obj_id)


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
    form = EveFittingRefitInlineForm
    extra = 0
    show_change_link = True
    fields = (
        "name",
        "eft_format",
        "description",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("name", "created_at", "updated_at")


@admin.register(EveFitting)
class EveFittingAdmin(ApprovalQueuedAdminMixin, SafeDeleteAdmin):
    """Admin for EveFitting. Ship and display name are inferred from EFT."""

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
        "name",
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
                "description": (
                    "Name matches the EFT header ([ShipName, Fitting name]) "
                    "and cannot be edited separately."
                ),
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
            "Pods & refits",
            {
                "description": (
                    "Link EveFittingPod loadouts and manage refit variants on "
                    "this fitting. Legacy text pod fields remain for reference."
                ),
                "fields": ("pods", "minimum_pod", "recommended_pod"),
            },
        ),
    )
    inlines = (EveFittingRefitInline,)

    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(reverse("admin:fittings_manage_fittings"))

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
        tier = fitting_change_request_tier(obj)
        linked = effective_protection_tier(obj)
        if linked:
            return tier
        return f"{tier} (no doctrine link)"

    def _prepare_fitting_from_form(self, obj, form):
        eft_format = form.cleaned_data.get("eft_format") or getattr(
            obj, "eft_format", ""
        )
        if eft_format and eft_format.strip():
            derived_name = EveFitting.fitting_name_from_eft(eft_format)
            if derived_name:
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
            if not obj.name:
                messages.error(
                    request,
                    "Could not derive a fitting name from the EFT header.",
                )
                return
            if not obj.ship_id:
                messages.error(
                    request,
                    "Could not resolve ship type from the EFT header.",
                )
                return
            payload = build_fitting_payload_from_form(form)
            try:
                with transaction.atomic():
                    super().save_model(request, obj, form, change)
                    # Hold soft-deleted until create is approved.
                    EveFitting.objects.get(pk=obj.pk).delete()
                    req = submit_fitting_change_request(
                        obj,
                        change_kind="fitting_create",
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
                        "New fitting submitted for approval "
                        "(not live until approved). "
                        '<a href="{}">View request</a>.',
                        url,
                    ),
                )
                _mark_change_request_queued(request, url)
            return

        original = EveFitting.objects.get(pk=obj.pk)
        payload = build_fitting_payload_from_form(form, original)

        if not fitting_payload_changed(original, payload):
            # Legacy rows may have name ≠ EFT header; sync without approval.
            if obj.name and obj.name != original.name:
                original.name = obj.name
                original.save(update_fields=["name"])
                messages.info(
                    request,
                    f"Fitting name updated to match EFT: {obj.name}",
                )
                return
            messages.info(
                request,
                "No approval-required fitting fields were changed.",
            )
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

    def delete_model(self, request, obj):
        payload = build_fitting_payload_from_instance(obj)
        try:
            req = submit_fitting_change_request(
                obj,
                change_kind="fitting_delete",
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
                    "Fitting delete submitted for approval "
                    "(fitting still live). "
                    '<a href="{}">View request</a>.',
                    url,
                ),
            )
            _mark_change_request_queued(request, url)

    def delete_queryset(self, request, queryset):
        queued = 0
        for obj in queryset:
            payload = build_fitting_payload_from_instance(obj)
            try:
                req = submit_fitting_change_request(
                    obj,
                    change_kind="fitting_delete",
                    payload=payload,
                    user=request.user,
                )
            except (PermissionError, ValueError) as exc:
                messages.error(request, str(exc))
                return
            if req:
                notify_fitting_change_request_proposed.delay(req.pk)
                queued += 1
        if queued:
            messages.warning(
                request,
                f"{queued} fitting delete request(s) submitted for approval "
                "(fittings still live).",
            )

    def save_formset(self, request, form, formset, change):
        if formset.model is not EveFittingRefit:
            return super().save_formset(request, form, formset, change)

        if getattr(request, "_change_request_queued", False):
            _warn_if_refit_edited_after_fitting_queued(request, formset)
            _mark_refit_formset_handled(formset)
            return

        fitting = form.instance
        if not fitting.pk:
            super().save_formset(request, form, formset, change)
            return

        queued = False
        for inline_form in formset.forms:
            if not inline_form.cleaned_data:
                continue
            is_delete = inline_form.cleaned_data.get("DELETE")
            if is_delete:
                if inline_form.instance.pk:
                    q, abort = _queue_refit_delete_request(
                        request, fitting, inline_form, request.user
                    )
                    if abort:
                        _mark_refit_formset_handled(formset)
                        return
                    queued = queued or q
                continue

            if not inline_form.has_changed():
                continue

            q, abort = _queue_refit_upsert_request(
                request, fitting, inline_form, request.user
            )
            if abort:
                _mark_refit_formset_handled(formset)
                return
            queued = queued or q

        _mark_refit_formset_handled(formset)
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
        "version_display",
        "name",
        "created_at",
    )
    list_filter = ("fitting",)
    search_fields = ("name", "superseded_version_id", "fitting__name")
    raw_id_fields = ("fitting",)
    ordering = ("-created_at",)
    readonly_fields = (
        "fitting",
        "version_display",
        "name",
        "created_at",
        "snapshot_display",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "fitting",
                    "version_display",
                    "name",
                    "created_at",
                ),
            },
        ),
        ("Snapshot", {"fields": ("snapshot_display",)}),
    )

    @admin.display(description="Superseded version")
    def version_display(self, obj):
        version_id = obj.superseded_version_id or "—"
        if len(version_id) <= 12:
            return version_id
        return format_html(
            '<span title="{}">{}…</span>',
            version_id,
            version_id[:12],
        )

    @admin.display(description="Snapshot")
    def snapshot_display(self, obj):
        if obj is None:
            return "—"
        return format_fitting_history_html(obj)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ChangeRequestAdminMixin:
    """Approve / reject / cancel actions for change request admins."""

    def changelist_view(self, request, extra_context=None):
        if "status" not in request.GET and "status__exact" not in request.GET:
            q = request.GET.copy()
            q["status__exact"] = ChangeRequestStatus.PENDING
            return HttpResponseRedirect(f"{request.path}?{q.urlencode()}")
        return super().changelist_view(request, extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        self.request = request
        return super().change_view(request, object_id, form_url, extra_context)

    def _review_action_choices(
        self, user, change_request
    ) -> list[tuple[str, str]]:
        choices = [
            (ChangeRequestReviewForm.REVIEW_ACTION_NONE, "— No action —")
        ]
        if self._user_can_review_request(user, change_request):
            choices.append(
                (ChangeRequestReviewForm.REVIEW_ACTION_APPROVE, "Approve")
            )
            choices.append(
                (ChangeRequestReviewForm.REVIEW_ACTION_REJECT, "Reject")
            )
        if self._user_can_cancel_request(user, change_request):
            choices.append(
                (
                    ChangeRequestReviewForm.REVIEW_ACTION_CANCEL,
                    "Cancel request",
                )
            )
        return choices

    def get_form(self, request, obj=None, change=False, **kwargs):
        base_form = kwargs.get("form", self.form)
        model_admin = self

        class RequestForm(base_form):
            def __init__(self, *args, **form_kwargs):
                super().__init__(*args, **form_kwargs)
                instance = self.instance
                if (
                    instance.pk
                    and instance.status == ChangeRequestStatus.PENDING
                ):
                    self.fields["review_action"].choices = (
                        model_admin._review_action_choices(
                            request.user, instance
                        )
                    )
                    if model_admin._is_self_approval(request.user, instance):
                        self.fields["review_action"].help_text = (
                            f"{_SELF_APPROVAL_WARNING} Choose Approve and "
                            "click Save to continue."
                        )
                else:
                    self.fields["review_action"].widget = forms.HiddenInput()
                    self.fields["review_action"].required = False

        kwargs["form"] = RequestForm
        return super().get_form(request, obj, change=change, **kwargs)

    def get_fieldsets(self, request, obj=None):
        review_fields = [
            "review_action",
            "submitted_by",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
        ]
        if not obj or obj.status != ChangeRequestStatus.PENDING:
            review_fields = [
                field for field in review_fields if field != "review_action"
            ]
        entity_fields = self._change_request_entity_fields()
        return (
            (None, {"fields": entity_fields}),
            (
                "Proposed changes",
                {
                    "fields": ("payload_display",),
                    "description": (
                        "Review what will change if this request is approved."
                    ),
                },
            ),
            ("Review", {"fields": tuple(review_fields)}),
        )

    def _change_request_entity_fields(self) -> tuple[str, ...]:
        raise NotImplementedError

    def save_model(self, request, obj, form, change):
        action = form.cleaned_data.get("review_action", "")
        if not action:
            return
        try:
            self._process_review_action(request, obj, action)
        except (PermissionDenied, ValueError) as exc:
            messages.error(request, str(exc))
            return
        if action == ChangeRequestReviewForm.REVIEW_ACTION_APPROVE:
            messages.success(request, "Change request approved.")
            if self._is_self_approval(request.user, obj):
                messages.warning(request, _SELF_APPROVAL_WARNING)
        elif action == ChangeRequestReviewForm.REVIEW_ACTION_REJECT:
            messages.success(request, "Change request rejected.")
        elif action == ChangeRequestReviewForm.REVIEW_ACTION_CANCEL:
            messages.success(request, "Change request cancelled.")

    def _process_review_action(self, request, change_request, action: str):
        if change_request.status != ChangeRequestStatus.PENDING:
            raise ValueError("Only pending requests can be updated.")
        if action == ChangeRequestReviewForm.REVIEW_ACTION_APPROVE:
            self._approve_change_request(request, change_request)
        elif action == ChangeRequestReviewForm.REVIEW_ACTION_REJECT:
            self._reject_change_request(request, change_request)
        elif action == ChangeRequestReviewForm.REVIEW_ACTION_CANCEL:
            self._cancel_change_request(request, change_request)
        else:
            raise ValueError(f"Unknown review action: {action}")

    def response_change(self, request, obj):
        if request.POST.get("review_action"):
            return HttpResponseRedirect(request.path)
        return super().response_change(request, obj)

    def _user_has_approve_permission(self, user, change_request) -> bool:
        tier = change_request.tier
        if isinstance(change_request, EveDoctrineChangeRequest):
            return can_approve_doctrine_request(user, tier)
        return can_approve_fitting_request(user, tier)

    def _user_can_self_approve(self, user, change_request) -> bool:
        if change_request.submitted_by_id != user.id:
            return False
        tier = change_request.tier
        if isinstance(change_request, EveDoctrineChangeRequest):
            return can_propose_doctrine_change(user, tier)
        return can_propose_fitting_change(user, tier)

    def _is_self_approval(self, user, change_request) -> bool:
        return change_request.submitted_by_id == user.id

    def _user_can_review_request(self, user, change_request) -> bool:
        return self._user_has_approve_permission(
            user, change_request
        ) or self._user_can_self_approve(user, change_request)

    def _user_can_cancel_request(self, user, change_request) -> bool:
        return user.is_superuser or change_request.submitted_by_id == user.id

    def _approve_change_request(self, request, change_request):
        self._check_approve(request, change_request)
        if isinstance(change_request, EveDoctrineChangeRequest):
            approve_doctrine_change_request(change_request, request.user)
        else:
            approve_fitting_change_request(change_request, request.user)

    def _reject_change_request(
        self, request, change_request, review_note: str = ""
    ):
        self._check_approve(request, change_request)
        if isinstance(change_request, EveDoctrineChangeRequest):
            reject_doctrine_change_request(
                change_request, request.user, review_note=review_note
            )
        else:
            reject_fitting_change_request(
                change_request, request.user, review_note=review_note
            )

    def _cancel_change_request(self, request, change_request):
        if not self._user_can_cancel_request(request.user, change_request):
            raise PermissionDenied(
                "You can only cancel your own pending requests."
            )
        if isinstance(change_request, EveDoctrineChangeRequest):
            cancel_doctrine_change_request(change_request, request.user)
        else:
            cancel_fitting_change_request(change_request, request.user)

    @admin.display(description="Proposed changes")
    def payload_display(self, obj):
        if obj is None:
            return "—"
        if isinstance(obj, EveDoctrineChangeRequest):
            return format_doctrine_change_request_html(obj)
        return format_fitting_change_request_html(obj)

    def _check_approve(self, request, change_request):
        if self._user_can_review_request(request.user, change_request):
            return
        if isinstance(change_request, EveDoctrineChangeRequest):
            raise PermissionDenied(
                "You cannot approve this doctrine change request."
            )
        raise PermissionDenied(
            "You cannot approve this fitting change request."
        )

    @admin.action(description="Approve selected pending requests")
    def approve_requests(self, request, queryset):
        pending = queryset.filter(status=ChangeRequestStatus.PENDING)
        count = 0
        self_approved = 0
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
                if self._is_self_approval(request.user, change_request):
                    self_approved += 1
            except (PermissionDenied, ValueError) as exc:
                messages.error(request, str(exc))
                return
        messages.success(request, f"Approved {count} request(s).")
        if self_approved:
            messages.warning(
                request,
                f"Approved {self_approved} of your own request(s). "
                f"{_SELF_APPROVAL_WARNING}",
            )

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
    form = EveDoctrineChangeRequestAdminForm
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
        "status",
        "change_kind",
        "payload_display",
        "submitted_by",
        "submitted_at",
        "reviewed_by",
        "reviewed_at",
    )
    actions = ["approve_requests", "reject_requests", "cancel_requests"]

    def _change_request_entity_fields(self):
        return ("doctrine", "tier", "status", "change_kind")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(EveFittingChangeRequest)
class EveFittingChangeRequestAdmin(ChangeRequestAdminMixin, admin.ModelAdmin):
    form = EveFittingChangeRequestAdminForm
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
        "status",
        "change_kind",
        "payload_display",
        "submitted_by",
        "submitted_at",
        "reviewed_by",
        "reviewed_at",
    )
    actions = ["approve_requests", "reject_requests", "cancel_requests"]

    def _change_request_entity_fields(self):
        return ("fitting", "refit", "tier", "status", "change_kind")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff


@admin.register(EveDoctrineHistory)
class EveDoctrineHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "doctrine",
        "version_display",
        "name",
        "type_display",
        "created_at",
    )
    list_filter = ("doctrine", "type")
    search_fields = ("name", "doctrine__name")
    raw_id_fields = ("doctrine",)
    ordering = ("-created_at",)
    readonly_fields = (
        "doctrine",
        "version_display",
        "name",
        "type_display",
        "created_at",
        "snapshot_display",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "doctrine",
                    "version_display",
                    "name",
                    "type_display",
                    "created_at",
                ),
            },
        ),
        ("Snapshot", {"fields": ("snapshot_display",)}),
    )

    @admin.display(description="Superseded version")
    def version_display(self, obj):
        version_id = obj.superseded_version_id or "—"
        if len(version_id) <= 12:
            return version_id
        return format_html(
            '<span title="{}">{}…</span>',
            version_id,
            version_id[:12],
        )

    @admin.display(description="Type")
    def type_display(self, obj):
        return DOCTRINE_TYPE_LABELS.get(obj.type, obj.type or "—")

    @admin.display(description="Snapshot")
    def snapshot_display(self, obj):
        if obj is None:
            return "—"
        return format_doctrine_history_html(obj)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
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

    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(reverse("admin:fittings_manage_doctrines"))

    def save_model(self, request, obj, form, change):
        payload = build_doctrine_payload_from_form(form.cleaned_data)

        if not change:
            tier = protection_tier_for_doctrine(obj)
            if tier is None:
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
        if tier is None:
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

    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(reverse("admin:fittings_manage_fittings"))


FITTINGS_HIDDEN_ADMIN_MODELS = {
    "evefitting",
    "evedoctrine",
    "evefittingpod",
}

FITTINGS_EXTRA_INDEX_LINKS = [
    {
        "name": "Fittings",
        "admin_url": "admin:fittings_manage_fittings",
        "can_view": user_can_view_fittings_admin,
    },
    {
        "name": "Doctrines",
        "admin_url": "admin:fittings_manage_doctrines",
        "can_view": user_can_view_doctrines_admin,
    },
]

_FITTINGS_ADMIN_PATCHED_ATTR = "fittings_admin_patched"


def _build_fittings_index_models(
    model_entries: list[dict], request
) -> list[dict]:
    visible = [
        model
        for model in model_entries
        if model.get("object_name", "").lower()
        not in FITTINGS_HIDDEN_ADMIN_MODELS
    ]
    for extra in FITTINGS_EXTRA_INDEX_LINKS:
        can_view = extra["can_view"](request.user)
        visible.insert(
            0,
            {
                "name": extra["name"],
                "object_name": extra["name"],
                "perms": index_link_perms(request.user, can_view=can_view),
                "admin_url": reverse(extra["admin_url"]),
                "view_only": False,
            },
        )
    return visible


def _apply_fittings_app_list(app_list: list[dict], request) -> list[dict]:
    for app in app_list:
        if app["app_label"] == "fittings":
            app["models"] = _build_fittings_index_models(
                app["models"], request
            )
    return app_list


def _get_custom_fittings_admin_urls():
    return [
        path(
            "fittings/manage/fittings/",
            admin.site.admin_view(fittings_manage_view),
            name="fittings_manage_fittings",
        ),
        path(
            "fittings/manage/doctrines/",
            admin.site.admin_view(doctrines_manage_view),
            name="fittings_manage_doctrines",
        ),
    ]


def apply_fittings_admin_customizations():
    """Chain fittings admin URLs and sidebar after other app patches."""
    if getattr(admin.site, _FITTINGS_ADMIN_PATCHED_ATTR, False):
        return

    fittings_previous_get_app_list = admin.site.get_app_list

    def _fittings_get_app_list(request, app_label=None):
        app_list = fittings_previous_get_app_list(request, app_label)
        return _apply_fittings_app_list(app_list, request)

    admin.site.get_app_list = _fittings_get_app_list

    fittings_previous_get_urls = admin.site.get_urls

    def _fittings_get_urls():
        return _get_custom_fittings_admin_urls() + fittings_previous_get_urls()

    admin.site.get_urls = _fittings_get_urls
    setattr(admin.site, _FITTINGS_ADMIN_PATCHED_ATTR, True)
