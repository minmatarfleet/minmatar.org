from django import forms
from django.contrib import admin
from django.contrib import messages
from django.db.models import Max
from django.utils import timezone

from reddit import rotation, schedule
from reddit.client import RedditClient
from reddit.markdown import blocking_problems
from reddit.models import (
    RedditAccount,
    RedditPost,
    RedditPostTemplate,
    RedditSchedule,
    RedditScheduleChange,
)
from reddit.service import link_reddit_post_to_discord, RedditService

reddit_client = RedditClient()
reddit_service = RedditService()


class RedditPostTemplateAdminForm(forms.ModelForm):
    """On edit, populate flair dropdown from the instance's subreddit."""

    class Meta:
        model = RedditPostTemplate
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only fetch flairs when editing (instance has subreddit)
        if self.instance and self.instance.pk and self.instance.subreddit:
            subreddit = self.instance.subreddit
            flairs = reddit_client.get_link_flairs(subreddit)
            choices = [("", "---------")]
            current = getattr(self.instance, "flair_id", None)
            current_in_list = False
            for f in flairs:
                choices.append((f["id"], f["text"] or f["id"]))
                if str(f["id"]) == str(current):
                    current_in_list = True
            if current and not current_in_list:
                choices.append((current, f"(current: {current})"))
            self.fields["flair_id"].widget = forms.Select(choices=choices)
            self.fields["flair_id"].required = False
        else:
            self.fields["flair_id"].help_text = (
                "Save with a subreddit first; on next edit the flair dropdown will be set from that subreddit."
            )

    def clean_content(self):
        content = self.cleaned_data["content"]
        # Only on change, so older posts can still be rescheduled as-is.
        if "content" in self.changed_data:
            problems = blocking_problems(content)
            if problems:
                raise forms.ValidationError(
                    [
                        f"Line {p.line}: Reddit can't render {p.excerpt!r} "
                        f"({p.code.replace('_', ' ')})."
                        for p in problems
                    ]
                )
        return content


def _record_approval(template, user):
    if template.approved:
        template.approved_by = user
        template.approved_at = timezone.now()
    else:
        template.approved_by = None
        template.approved_at = None


class RedditPostInline(admin.TabularInline):
    """What happened each time the template came due (newest first)."""

    model = RedditPost
    extra = 0
    max_num = 0
    can_delete = False
    fields = [
        "slot_date",
        "scheduled_for",
        "status",
        "fallback_reason",
        "title",
        "reddit_url",
        "delivered_at",
    ]
    readonly_fields = fields
    ordering = ["-slot_date", "-created_at"]


@admin.register(RedditPostTemplate)
class RedditPostTemplateAdmin(admin.ModelAdmin):
    """A corporation's recurring Reddit post and its delivery history."""

    form = RedditPostTemplateAdminForm
    list_display = [
        "title",
        "corporation",
        "subreddit",
        "priority",
        "paused",
        "posting_window",
        "delivery_method",
        "approved",
        "discord_channel",
        "last_delivered_at",
    ]
    list_editable = ["priority", "paused", "posting_window"]
    list_filter = [
        "priority",
        "paused",
        "approved",
        "delivery_method",
        "subreddit",
    ]
    list_select_related = ["corporation", "discord_channel"]
    search_fields = ["title", "corporation__name", "corporation__ticker"]
    autocomplete_fields = ["corporation", "discord_channel"]
    readonly_fields = [
        "approved_by",
        "approved_at",
        "updated_at",
    ]
    inlines = [RedditPostInline]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(last_delivered_at=Max("posts__delivered_at"))
        )

    @admin.display(ordering="last_delivered_at")
    def last_delivered_at(self, obj):
        return obj.last_delivered_at

    actions = [
        "action_approve",
        "action_manually_submit_post",
        "action_manually_link_to_discord",
    ]

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            fields.append("approved")
        return fields

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            actions.pop("action_approve", None)
        return actions

    def save_model(self, request, obj, form, change):
        if "approved" in form.changed_data:
            _record_approval(obj, request.user)
        super().save_model(request, obj, form, change)
        # Priority, pausing and the window show in the drafts straight away.
        schedule.refresh_drafts()

    @admin.action(description="Approve for automatic posting")
    def action_approve(self, request, queryset):
        if not request.user.is_superuser:
            return
        count = 0
        for template in queryset.filter(approved=False):
            template.approved = True
            _record_approval(template, request.user)
            template.save()
            count += 1
        self.message_user(
            request, f"Approved {count} post(s).", messages.SUCCESS
        )

    @admin.action(description="Manually submit post")
    def action_manually_submit_post(self, request, queryset):
        done = 0
        for template in queryset:
            try:
                post = reddit_service.post_recriutment_ad(template)
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to submit '{template.title}': {e}",
                    messages.ERROR,
                )
                continue
            if post.status == RedditPost.POSTED:
                done += 1
            else:
                self.message_user(
                    request,
                    f"Reddit rejected '{template.title}'.",
                    messages.ERROR,
                )
        if done:
            self.message_user(
                request,
                f"Submitted {done} post(s) to Reddit.",
                messages.SUCCESS,
            )

    @admin.action(description="Manually link to Discord")
    def action_manually_link_to_discord(self, request, queryset):
        done = 0
        skipped = 0
        for template in queryset:
            if not template.discord_channel_id:
                skipped += 1
                continue
            post = (
                template.posts.filter(status=RedditPost.POSTED)
                .exclude(reddit_url="")
                .first()
            )
            if post is None:
                self.message_user(
                    request,
                    f"'{template.title}' has never been posted to Reddit. "
                    "Submit a post first.",
                    messages.WARNING,
                )
                skipped += 1
                continue
            if link_reddit_post_to_discord(
                template, post.reddit_url, post.title
            ):
                done += 1
        if done:
            self.message_user(
                request,
                f"Linked {done} post(s) to Discord.",
                messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request,
                f"Skipped {skipped} (no channel or no last post).",
                messages.WARNING,
            )


class SlotForm(forms.ModelForm):
    """A confirmed slot still ahead can be moved to another corporation or
    time; anything else is read-only."""

    class Meta:
        model = RedditPost
        fields = ["template", "scheduled_for"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        post = self.instance
        self.editable = bool(
            post.pk
            and post.status == RedditPost.CONFIRMED
            and post.scheduled_for
            and post.scheduled_for > timezone.now()
        )
        if not self.editable:
            for field in self.fields.values():
                field.disabled = True

    def clean(self):
        cleaned = super().clean()
        template = cleaned.get("template")
        when = cleaned.get("scheduled_for")
        if not self.editable or not template or not when:
            return cleaned
        if not self.has_changed():
            return cleaned
        clash = (
            RedditPost.objects.filter(
                template=template, status__in=schedule.LIVE_STATUSES
            )
            .exclude(pk=self.instance.pk)
            .filter(
                scheduled_for__gt=when - rotation.COOLDOWN,
                scheduled_for__lt=when + rotation.COOLDOWN,
            )
            .first()
        )
        if clash:
            raise forms.ValidationError(
                f"{template.corporation.name} already posts on "
                f"{clash.scheduled_for:%d %b}; slots must be at least "
                f"{rotation.COOLDOWN.days} days apart."
            )
        return cleaned


class SlotInline(admin.TabularInline):
    model = RedditPost
    form = SlotForm
    fk_name = "schedule"
    extra = 0
    max_num = 0
    can_delete = False
    fields = [
        "slot_date",
        "template",
        "scheduled_for",
        "status",
        "heads_up_sent_at",
        "fallback_reason",
    ]
    readonly_fields = [
        "slot_date",
        "status",
        "heads_up_sent_at",
        "fallback_reason",
    ]
    ordering = ["slot_date"]
    autocomplete_fields = ["template"]


class ScheduleChangeInline(admin.TabularInline):
    model = RedditScheduleChange
    extra = 0
    max_num = 0
    can_delete = False
    fields = [
        "created_at",
        "slot_date",
        "from_template",
        "to_template",
        "reason",
        "detail",
    ]
    readonly_fields = fields


@admin.register(RedditSchedule)
class RedditScheduleAdmin(admin.ModelAdmin):
    """The rotation, month by month. Drafts are worked out automatically;
    move a published slot by editing it here."""

    list_display = [
        "month",
        "status",
        "slot_count",
        "generated_at",
        "published_at",
    ]
    list_filter = ["status"]
    readonly_fields = [
        "month",
        "status",
        "weights",
        "quotas",
        "inputs_hash",
        "generated_at",
        "published_at",
        "published_by",
    ]
    inlines = [SlotInline, ScheduleChangeInline]
    actions = ["action_publish", "action_regenerate"]

    def has_add_permission(self, request):
        return False

    @admin.display(description="Slots")
    def slot_count(self, obj):
        return obj.slots.count()

    def changelist_view(self, request, extra_context=None):
        # Opening the list makes sure this month and next have drafts.
        schedule.refresh_drafts()
        return super().changelist_view(request, extra_context)

    def save_formset(self, request, form, formset, change):
        moves = []
        for slot_form in formset.forms:
            if not getattr(slot_form, "editable", False):
                continue
            if not slot_form.has_changed():
                continue
            old_template = RedditPostTemplate.objects.get(
                pk=slot_form.initial["template"]
            )
            moves.append(
                (
                    slot_form.instance,
                    old_template,
                    slot_form.initial["scheduled_for"],
                )
            )
        super().save_formset(request, form, formset, change)
        for post, old_template, old_time in moves:
            schedule.move_slot(
                post, post.template, post.scheduled_for, old_template, old_time
            )

    @admin.action(description="Publish (confirm slots and DM each CEO)")
    def action_publish(self, request, queryset):
        for month in queryset.filter(status=RedditSchedule.DRAFT):
            confirmed = schedule.publish(month, user=request.user)
            self.message_user(
                request,
                f"Published {month.month:%B %Y}: {confirmed} slot(s).",
                messages.SUCCESS,
            )

    @admin.action(description="Work out the draft again")
    def action_regenerate(self, request, queryset):
        drafts = queryset.filter(status=RedditSchedule.DRAFT)
        drafts.update(inputs_hash="")
        for month in drafts:
            schedule.refresh_month(month.month, timezone.now())
        self.message_user(
            request, f"Updated {drafts.count()} draft(s).", messages.SUCCESS
        )


@admin.register(RedditPost)
class RedditPostAdmin(admin.ModelAdmin):
    """Read-only log of every Reddit post and reminder."""

    list_display = [
        "template",
        "slot_date",
        "scheduled_for",
        "status",
        "fallback_reason",
        "reddit_url",
        "delivered_at",
    ]
    list_filter = ["status", "fallback_reason", "schedule"]
    list_select_related = ["template__corporation"]
    search_fields = ["template__title", "template__corporation__name"]
    date_hierarchy = "scheduled_for"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(RedditAccount)
class RedditAccountAdmin(admin.ModelAdmin):
    """Linked Reddit accounts. The refresh token is never displayed."""

    list_display = ["reddit_username", "user", "token_invalid", "updated_at"]
    search_fields = ["reddit_username", "user__username"]
    exclude = ["refresh_token"]
    readonly_fields = [
        "user",
        "reddit_username",
        "scopes",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        return False
