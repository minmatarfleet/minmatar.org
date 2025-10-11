from django.contrib import admin

from reddit.models import RedditScheduledPost


class RedditPostAdmin(admin.ModelAdmin):
    """Custom admin model for RedditScheduledPost entities"""

    list_display = [
        "title",
        "subreddit",
        "posting_day",
        "last_post_at",
    ]

    readonly_fields = ("last_post_at", "updated_at", "latest_comment_url", "latest_fullname")


admin.site.register(RedditScheduledPost, RedditPostAdmin)
