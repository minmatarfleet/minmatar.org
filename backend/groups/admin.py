import csv
import io

from django.contrib import admin
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.urls import path

from discord.models import DiscordUser
from eveonline.helpers.characters import user_primary_character
from eveonline.models import EveCorporation

from .models import (
    AffiliationType,
    EveCorporationGroup,
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


class CorporationFilter(admin.SimpleListFilter):
    """Filter UserCommunityStatus by primary character's corporation."""

    title = "corporation"
    parameter_name = "corporation"

    def lookups(self, request, model_admin):
        # Only corporations in our alliances (EveAlliance)
        alliance_corp_ids = EveCorporation.objects.filter(
            alliance__isnull=False,
        ).values_list("corporation_id", flat=True)
        # Of those, corporations that have at least one community status user with that corp as primary
        corp_ids = (
            UserCommunityStatus.objects.filter(
                user__eveplayer__primary_character__corporation_id__in=alliance_corp_ids,
            )
            .values_list(
                "user__eveplayer__primary_character__corporation_id", flat=True
            )
            .distinct()
        )
        corps = (
            EveCorporation.objects.filter(corporation_id__in=corp_ids)
            .order_by("name")
            .values_list("corporation_id", "name")
        )
        return [(cid, name or str(cid)) for cid, name in corps]

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset
        return queryset.filter(
            user__eveplayer__primary_character__corporation_id=value,
        )


@admin.register(UserCommunityStatus)
class UserCommunityStatusAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "status",
        "primary_character_name",
        "corporation",
        "days_in_community",
    )
    list_filter = ("status", CorporationFilter)
    search_fields = ("user__username",)
    readonly_fields = (
        "primary_character_name",
        "corporation",
        "days_in_community",
    )
    fieldsets = (
        (None, {"fields": ("user", "status")}),
        (
            "Community info",
            {
                "fields": (
                    "primary_character_name",
                    "corporation",
                    "days_in_community",
                ),
                "description": "Derived from primary character and Discord.",
            },
        ),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "user__eveplayer__primary_character")

    def primary_character_name(self, obj):
        if not obj or not obj.user:
            return "—"
        primary = user_primary_character(obj.user)
        return primary.character_name if primary else "—"

    primary_character_name.short_description = "Primary character"

    def corporation(self, obj):
        if not obj or not obj.user:
            return "—"
        primary = user_primary_character(obj.user)
        if not primary or not primary.corporation_id:
            return "—"
        corp = (
            EveCorporation.objects.filter(
                corporation_id=primary.corporation_id
            )
            .values_list("name", flat=True)
            .first()
        )
        return corp or str(primary.corporation_id)

    corporation.short_description = "Corporation"

    def days_in_community(self, obj):
        if not obj or not obj.user:
            return "—"
        try:
            discord_user = DiscordUser.objects.get(user=obj.user)
        except DiscordUser.DoesNotExist:
            return "—"
        if not discord_user.created_at:
            return "—"
        delta = (timezone.now() - discord_user.created_at).days
        return delta

    days_in_community.short_description = "Days in community"

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
