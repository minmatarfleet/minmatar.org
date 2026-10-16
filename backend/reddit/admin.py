from django import forms
from django.contrib import admin
from django.contrib import messages
from django.utils import timezone

from reddit.client import RedditClient
from reddit.markdown import blocking_problems
from reddit.models import RedditAccount, RedditScheduledPost
from reddit.service import link_reddit_post_to_discord, RedditService

reddit_client = RedditClient()
reddit_service = RedditService()


class RedditScheduledPostAdminForm(forms.ModelForm):
    """On edit, populate flair dropdown from the instance's subreddit."""

    class Meta:
        model = RedditScheduledPost
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


def _record_approval(scheduled_post, user):
    if scheduled_post.approved:
        scheduled_post.approved_by = user
        scheduled_post.approved_at = timezone.now()
    else:
        scheduled_post.approved_by = None
        scheduled_post.approved_at = None


class RedditPostAdmin(admin.ModelAdmin):
    """Custom admin model for RedditScheduledPost entities"""

    form = RedditScheduledPostAdminForm
    list_display = [
        "title",
        "corporation",
        "subreddit",
        "posting_day",
        "posting_time",
        "delivery_method",
        "approved",
        "last_post_at",
        "last_reminder_at",
    ]
    list_filter = ["approved", "delivery_method", "posting_day", "subreddit"]
    search_fields = ["title", "corporation__name"]
    autocomplete_fields = ["corporation"]
    readonly_fields = [
        "approved_by",
        "approved_at",
        "last_scheduled_on",
        "updated_at",
    ]
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
        for scheduled_post in queryset.filter(approved=False):
            scheduled_post.approved = True
            _record_approval(scheduled_post, request.user)
            scheduled_post.save()
            count += 1
        self.message_user(
            request, f"Approved {count} post(s).", messages.SUCCESS
        )

    @admin.action(description="Manually submit post")
    def action_manually_submit_post(self, request, queryset):
        done = 0
        for scheduled_post in queryset:
            try:
                reddit_service.post_recriutment_ad(scheduled_post)
                done += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to submit '{scheduled_post.title}': {e}",
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
        for scheduled_post in queryset:
            if not scheduled_post.discord_channel_id:
                skipped += 1
                continue
            url = scheduled_post.last_reddit_post_url
            title = scheduled_post.last_reddit_post_title
            if not url or not title:
                self.message_user(
                    request,
                    f"'{scheduled_post.title}' has no last Reddit post URL/title. Submit a post first.",
                    messages.WARNING,
                )
                skipped += 1
                continue
            if link_reddit_post_to_discord(scheduled_post, url, title):
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


admin.site.register(RedditScheduledPost, RedditPostAdmin)


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
