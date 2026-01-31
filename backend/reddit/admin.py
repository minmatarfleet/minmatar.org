from django import forms
from django.contrib import admin
from django.contrib import messages

from reddit.client import RedditClient
from reddit.models import RedditScheduledPost
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


class RedditPostAdmin(admin.ModelAdmin):
    """Custom admin model for RedditScheduledPost entities"""

    form = RedditScheduledPostAdminForm
    list_display = [
        "title",
        "subreddit",
        "posting_day",
        "discord_channel_id",
        "flair_id",
        "last_post_at",
        "last_reddit_post_url",
    ]
    list_filter = ["posting_day", "subreddit"]
    actions = [
        "action_manually_submit_post",
        "action_manually_link_to_discord",
    ]

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
