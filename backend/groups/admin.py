import csv
import io

from django.contrib import admin
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.urls import path

from .models import (
    AffiliationType,
    EveCorporationGroup,
    Sig,
    Team,
    UserCommunityStatus,
    UserCommunityStatusHistory,
)
from .tasks import bulk_update_community_status

User = get_user_model()

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
        bulk_update_community_status.delay(content, reason, request.user.id)
        self.message_user(
            request,
            "Bulk update started. Processing runs in the background; Discord role updates may take a few minutes. Check logs for applied/not_found/errors.",
            messages.SUCCESS,
        )
        return render(
            request,
            "admin/groups/usercommunitystatus/bulk_upload.html",
            _bulk_upload_context(self, "Bulk update community status"),
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
