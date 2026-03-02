import csv
import io

from django.contrib import admin
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.urls import path

from .helpers import sync_user_community_groups
from .models import (
    AffiliationType,
    EveCorporationGroup,
    Sig,
    Team,
    UserCommunityStatus,
    UserCommunityStatusHistory,
)

User = get_user_model()

VALID_STATUSES = {"active", "trial", "on_leave"}

# Register your models here.
admin.site.register(AffiliationType)
admin.site.register(EveCorporationGroup)


def _bulk_upload_context(admin_instance, title, summary=None):
    """Build template context for bulk upload view. Uses model._meta (Django API)."""
    opts = admin_instance.model._meta  # pylint: disable=protected-access
    ctx = {
        "opts": opts,
        "title": title,
    }
    if summary is not None:
        ctx["summary"] = summary
    return ctx


def _process_bulk_row(row, row_num, default_reason, request_user):
    """
    Process one CSV row. Returns (applied, not_found_name, error_msg).
    applied=True means we updated the user and caller should count and sync.
    """
    username = (row.get("username") or "").strip()
    status = (row.get("community_status") or "").strip().lower()
    row_reason = (row.get("reason") or default_reason).strip()
    if not username:
        return (False, None, None)
    if status not in VALID_STATUSES:
        return (
            False,
            None,
            f"Row {row_num}: invalid status '{status}' for {username}",
        )
    user = User.objects.filter(username=username).first()
    if not user:
        return (False, username, None)
    ucs, created = UserCommunityStatus.objects.get_or_create(
        user=user, defaults={"status": status}
    )
    if not created and ucs.status != status:
        ucs.status = status
        ucs.save()
    latest = (
        UserCommunityStatusHistory.objects.filter(user=user)
        .order_by("-changed_at")
        .first()
    )
    if latest:
        latest.changed_by = request_user
        latest.reason = row_reason or "bulk upload"
        latest.save(update_fields=["changed_by", "reason"])
    sync_user_community_groups(user)
    return (True, None, None)


@admin.register(UserCommunityStatus)
class UserCommunityStatusAdmin(admin.ModelAdmin):
    list_display = ("user", "status")
    list_filter = ("status",)
    search_fields = ("user__username",)

    def get_urls(self):
        urls = super().get_urls()
        return [
            path(
                "bulk-upload/",
                self.admin_site.admin_view(self.bulk_upload_view),
                name="groups_usercommunitystatus_bulk_upload",
            ),
        ] + urls

    def bulk_upload_view(self, request):
        if request.method != "POST":
            return render(
                request,
                "admin/groups/usercommunitystatus/bulk_upload.html",
                _bulk_upload_context(self, "Bulk update community status"),
            )
        csv_file = request.FILES.get("csv_file")
        reason = (request.POST.get("reason") or "").strip()
        if not csv_file:
            self.message_user(request, "No CSV file provided.", messages.ERROR)
            return render(
                request,
                "admin/groups/usercommunitystatus/bulk_upload.html",
                _bulk_upload_context(self, "Bulk update community status"),
            )
        try:
            content = csv_file.read().decode("utf-8-sig")
        except Exception as e:
            self.message_user(
                request, f"Could not read CSV: {e}", messages.ERROR
            )
            return render(
                request,
                "admin/groups/usercommunitystatus/bulk_upload.html",
                _bulk_upload_context(self, "Bulk update community status"),
            )
        reader = csv.DictReader(io.StringIO(content))
        if (
            "username" not in reader.fieldnames
            or "community_status" not in reader.fieldnames
        ):
            self.message_user(
                request,
                "CSV must have columns: username, community_status (optional: reason).",
                messages.ERROR,
            )
            return render(
                request,
                "admin/groups/usercommunitystatus/bulk_upload.html",
                _bulk_upload_context(self, "Bulk update community status"),
            )
        applied = 0
        not_found = []
        errors = []
        for i, row in enumerate(reader, start=2):
            did_apply, not_found_name, error_msg = _process_bulk_row(
                row, i, reason, request.user
            )
            if did_apply:
                applied += 1
            elif not_found_name:
                not_found.append(not_found_name)
            elif error_msg:
                errors.append(error_msg)
        msg_parts = [f"Applied {applied} row(s)."]
        if not_found:
            msg_parts.append(
                f"Usernames not found ({len(not_found)}): {', '.join(not_found[:10])}{'…' if len(not_found) > 10 else ''}"
            )
        if errors:
            msg_parts.append(
                f"Errors: {'; '.join(errors[:5])}{'…' if len(errors) > 5 else ''}"
            )
        if not_found or errors:
            self.message_user(request, " ".join(msg_parts), messages.WARNING)
        else:
            self.message_user(request, msg_parts[0], messages.SUCCESS)
        return render(
            request,
            "admin/groups/usercommunitystatus/bulk_upload.html",
            _bulk_upload_context(
                self,
                "Bulk update community status",
                summary={
                    "applied": applied,
                    "not_found": not_found,
                    "errors": errors,
                },
            ),
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        latest = (
            UserCommunityStatusHistory.objects.filter(user=obj.user)
            .order_by("-changed_at")
            .first()
        )
        if latest and latest.changed_by is None:
            latest.changed_by = request.user
            latest.save(update_fields=["changed_by"])

    @admin.action(description="Approve trial (set to Active)")
    def approve_trial(self, request, queryset):
        trial_qs = queryset.filter(status=UserCommunityStatus.STATUS_TRIAL)
        count = trial_qs.count()
        for ucs in trial_qs:
            ucs.status = UserCommunityStatus.STATUS_ACTIVE
            ucs.save()
        self.message_user(
            request, f"Approved {count} trial member(s).", messages.SUCCESS
        )

    @admin.action(description="Set selected to On Leave")
    def set_on_leave(self, request, queryset):
        for ucs in queryset:
            ucs.status = UserCommunityStatus.STATUS_ON_LEAVE
            ucs.save()
        self.message_user(
            request,
            f"Set {queryset.count()} member(s) to On Leave.",
            messages.SUCCESS,
        )

    actions = [approve_trial, set_on_leave]


@admin.register(UserCommunityStatusHistory)
class UserCommunityStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "from_status",
        "to_status",
        "changed_at",
        "changed_by",
        "reason",
    )
    list_filter = ("to_status",)
    search_fields = ("user__username",)
    readonly_fields = (
        "user",
        "from_status",
        "to_status",
        "changed_at",
        "changed_by",
        "reason",
    )
    ordering = ("-changed_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description", "content")
    ordering = ("name",)
    filter_horizontal = ("directors", "members")


@admin.register(Sig)
class SigAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description", "content")
    ordering = ("name",)
    filter_horizontal = ("officers", "members")
