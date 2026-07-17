from django.contrib import admin
from django.utils.html import format_html, format_html_join

from page_progress.models import UserPageProgress, UserPageSectionProgress


class AcknowledgedFilter(admin.SimpleListFilter):
    title = "acknowledgement"
    parameter_name = "acknowledged"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Acknowledged"),
            ("no", "In progress"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(acknowledged_at__isnull=False)
        if self.value() == "no":
            return queryset.filter(acknowledged_at__isnull=True)
        return queryset


@admin.register(UserPageProgress)
class UserPageProgressAdmin(admin.ModelAdmin):
    list_display = ("username", "page", "progress_percent")
    list_filter = ("page_key", AcknowledgedFilter)
    search_fields = ("user__username", "page_key", "page_title")
    readonly_fields = (
        "user",
        "page_key",
        "page_title",
        "version",
        "section_total",
        "started_at",
        "last_seen_at",
        "acknowledged_at",
        "progress_percent",
        "sections_read",
    )
    fields = (
        "user",
        "page_key",
        "page_title",
        "version",
        "progress_percent",
        "section_total",
        "sections_read",
        "started_at",
        "last_seen_at",
        "acknowledged_at",
    )
    ordering = ("-last_seen_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    @admin.display(description="Username", ordering="user__username")
    def username(self, obj: UserPageProgress) -> str:
        return obj.user.username

    @admin.display(description="Page", ordering="page_title")
    def page(self, obj: UserPageProgress) -> str:
        title = (obj.page_title or "").strip()
        if title:
            return title
        return obj.page_key

    @admin.display(description="Progress")
    def progress_percent(self, obj: UserPageProgress) -> str:
        return format_html("{}%", obj.percent)

    @admin.display(description="Sections read")
    def sections_read(self, obj: UserPageProgress) -> str:
        sections = list(
            UserPageSectionProgress.objects.filter(
                user_id=obj.user_id,
                page_key=obj.page_key,
                version=obj.version,
            )
            .order_by("first_seen_at", "section_id")
            .values_list("section_id", "first_seen_at", "last_seen_at")
        )
        if not sections:
            return "—"

        rows = format_html_join(
            "",
            "<tr><td>{}</td><td>{}</td><td>{}</td></tr>",
            (
                (
                    section_id,
                    (
                        first_seen.strftime("%Y-%m-%d %H:%M")
                        if first_seen
                        else "—"
                    ),
                    last_seen.strftime("%Y-%m-%d %H:%M") if last_seen else "—",
                )
                for section_id, first_seen, last_seen in sections
            ),
        )
        return format_html(
            '<table style="width:auto;border-collapse:collapse">'
            "<thead><tr>"
            '<th style="text-align:left;padding:2px 12px 2px 0">Section</th>'
            '<th style="text-align:left;padding:2px 12px 2px 0">First seen</th>'
            '<th style="text-align:left;padding:2px 0">Last seen</th>'
            "</tr></thead><tbody>{}</tbody></table>"
            '<p style="margin:6px 0 0;color:#666">{} / {} sections</p>',
            rows,
            len(sections),
            obj.section_total,
        )
