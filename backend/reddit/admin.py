from django import forms
from django.contrib import admin
from django.contrib import messages
from django.db.models import Max
from django.utils import timezone

from reddit.client import RedditClient
from reddit.markdown import blocking_problems
from reddit.models import RedditAccount, RedditPost, RedditPostTemplate
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
        "scheduled_for",
        "status",
        "fallback_reason",
        "title",
        "reddit_url",
        "created_at",
    ]
    readonly_fields = fields
    ordering = ["-created_at"]


@admin.register(RedditPostTemplate)
class RedditPostTemplateAdmin(admin.ModelAdmin):
    """A corporation's recurring Reddit post and its delivery history."""

    form = RedditPostTemplateAdminForm
    list_display = [
        "title",
        "corporation",
        "subreddit",
        "posting_day",
        "posting_time",
        "delivery_method",
        "approved",
        "discord_channel",
        "last_delivered_at",
    ]
    list_filter = ["approved", "delivery_method", "posting_day", "subreddit"]
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
            .annotate(last_delivered_at=Max("posts__created_at"))
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


@admin.register(RedditPost)
class RedditPostAdmin(admin.ModelAdmin):
    """Read-only log of every Reddit post and reminder."""

    list_display = [
        "template",
        "scheduled_for",
        "status",
        "fallback_reason",
        "reddit_url",
        "created_at",
    ]
    list_filter = ["status", "fallback_reason"]
    list_select_related = ["template__corporation"]
    search_fields = ["template__title", "template__corporation__name"]
    date_hierarchy = "created_at"

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
